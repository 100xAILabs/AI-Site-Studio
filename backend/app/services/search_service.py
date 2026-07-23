import uuid
import httpx
import json
import os
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models

from app.core.config import settings
import logging
logger = logging.getLogger(__name__)
from app.repositories.template_repo import TemplateRepository
from app.schemas.template import TemplateCardResponse, TemplateFilterParams
from app.models.user import User
from app.models.analytics import AnalyticsEvent
from app.models.download import Download
from app.repositories.favorite_repo import FavoriteRepository, WishlistRepository
from app.models.template import Template
from sqlalchemy import select


# ── Module-level singleton Qdrant client ──────────────────────────────────
# Qdrant's local-disk mode uses an exclusive file lock on the storage folder.
# Creating a new client per request causes lock contention. We initialise once
# at module load time and reuse the same client for every SearchService instance.
_qdrant_client: Optional[AsyncQdrantClient] = None


def _get_shared_qdrant_client() -> AsyncQdrantClient:
    """Return (and lazily create) a process-wide Qdrant client singleton."""
    global _qdrant_client
    if _qdrant_client is None:
        url = settings.QDRANT_URL
        if url and "localhost" not in url and "127.0.0.1" not in url:
            _qdrant_client = AsyncQdrantClient(
                url=url,
                api_key=settings.QDRANT_API_KEY or None,
            )
        else:
            db_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "qdrant_storage"
            )
            os.makedirs(db_dir, exist_ok=True)
            # Remove stale lock files left by unclean shutdowns
            lock_file = os.path.join(db_dir, ".lock")
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                    logger.info(f"Removed stale Qdrant .lock file at: {lock_file}")
                except OSError:
                    pass
            logger.info(f"Using local disk-based Qdrant persistence at: {db_dir}")
            try:
                _qdrant_client = AsyncQdrantClient(path=db_dir)
            except Exception as e:
                logger.warning(
                    f"Local Qdrant storage locked ({e}). Falling back to in-memory client."
                )
                _qdrant_client = AsyncQdrantClient(location=":memory:")
    return _qdrant_client


class SearchService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.template_repo = TemplateRepository(db)

    @property
    def qdrant(self) -> AsyncQdrantClient:
        return _get_shared_qdrant_client()


    async def _get_gemini_embedding(self, text: str) -> List[float]:
        """Generate dense vector embedding using Gemini embedding API or Azure fallback."""
        from app.services.ai_service import ai_service
        return await ai_service.generate_embedding(text, "semantic_search")

    async def _ensure_collection(self) -> None:
        """Verify if Qdrant collection exists and has 3072 dimensions; recreate if mismatch."""
        try:
            info = await self.qdrant.get_collection(settings.QDRANT_COLLECTION)
            vectors_config = info.config.params.vectors
            
            # Extract size safely
            current_size = 0
            if hasattr(vectors_config, "size"):
                current_size = vectors_config.size
            elif isinstance(vectors_config, dict) and "size" in vectors_config:
                current_size = vectors_config["size"]
                
            if current_size != 3072:
                logger.info(f"Recreating Qdrant collection {settings.QDRANT_COLLECTION} with 3072 dimensions...")
                await self.qdrant.delete_collection(settings.QDRANT_COLLECTION)
                await self.qdrant.create_collection(
                    collection_name=settings.QDRANT_COLLECTION,
                    vectors_config=qdrant_models.VectorParams(
                        size=3072,
                        distance=qdrant_models.Distance.COSINE
                    )
                )
        except Exception:
            logger.info(f"Creating Qdrant collection {settings.QDRANT_COLLECTION} (3072 dimensions)...")
            await self.qdrant.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config=qdrant_models.VectorParams(
                    size=3072,
                    distance=qdrant_models.Distance.COSINE
                )
            )



    async def _log_search_event(self, query: str, user: Optional[User] = None) -> None:
        """Logs the search query event to the analytics table."""
        try:
            event = AnalyticsEvent(
                user_id=user.id if user else None,
                event_type="search",
                entity_type="template",
                properties={"q": query, "semantic": True}
            )
            self.db.add(event)
            await self.db.flush()
        except Exception as e:
            logger.error(f"Failed to log search event: {e}")

    async def _build_user_profile_context(self, user: User) -> str:
        """Builds a textual representation of the user's preferences based on their history."""
        context_parts = []
        try:
            # 1. Favorites
            fav_repo = FavoriteRepository(self.db)
            favorites = await fav_repo.get_user_favorites(user.id)
            if favorites:
                fav_titles = [f"'{t.title}' (Category: {t.category.name if t.category else 'N/A'}, Industry: {t.industry or 'N/A'}, Framework: {t.framework or 'N/A'})" for t in favorites[:5]]
                context_parts.append(f"Favorite Templates: {', '.join(fav_titles)}")
                
            # 2. Wishlist
            wish_repo = WishlistRepository(self.db)
            wishlist = await wish_repo.get_user_wishlist(user.id)
            if wishlist:
                wish_titles = [f"'{t.title}'" for t in wishlist[:5]]
                context_parts.append(f"Wishlisted Templates: {', '.join(wish_titles)}")

            # 3. Downloads
            download_result = await self.db.execute(
                select(Template)
                .join(Download, Download.template_id == Template.id)
                .where(Download.user_id == user.id)
                .order_by(Download.created_at.desc())
                .limit(5)
            )
            downloads = list(download_result.scalars().all())
            if downloads:
                dl_titles = [f"'{t.title}' (Framework: {t.framework or 'N/A'})" for t in downloads]
                context_parts.append(f"Downloaded/Purchased Templates: {', '.join(dl_titles)}")

            # 4. Recent Searches
            search_result = await self.db.execute(
                select(AnalyticsEvent)
                .where(AnalyticsEvent.user_id == user.id, AnalyticsEvent.event_type == "search")
                .order_by(AnalyticsEvent.created_at.desc())
                .limit(5)
            )
            searches = list(search_result.scalars().all())
            if searches:
                queries = [f"'{e.properties.get('q')}'" for e in searches if e.properties and e.properties.get("q")]
                if queries:
                    context_parts.append(f"Recent Search Queries: {', '.join(queries)}")
        except Exception as e:
            logger.error(f"Error compiling user profile context: {e}")

        if not context_parts:
            return "No previous interaction history."
            
        return "\n".join(context_parts)

    async def _rank_templates(self, query: str, templates_data: List[dict], user_profile_context: Optional[str] = None) -> List[uuid.UUID]:
        """Use RankGemini (gemini-3.5-flash) to re-rank the templates based on query relevance and user context."""
        from app.services.ai_service import ai_service, robust_json_loads
        if not ai_service.client or not templates_data:
            return [t["id"] for t in templates_data]

        # Format templates list for LLM context
        formatted_list = []
        for i, t in enumerate(templates_data):
            tags_str = ", ".join(t.get("tags", []))
            formatted_list.append(
                f"Index: {i}\nID: {t['id']}\nTitle: {t['title']}\nDescription: {t['description']}\nTags: {tags_str}\nIndustry: {t.get('industry', '')}\nStyle: {t.get('style', '')}\nColor: {t.get('color_scheme', '')}\n---"
            )
        templates_str = "\n".join(formatted_list)

        personalization_instruction = ""
        if user_profile_context:
            personalization_instruction = f"""
Historically, this user has the following interaction preferences/context:
{user_profile_context}

Please use this history to personalize the ranking. If multiple templates are highly relevant to the query, prioritize the ones that align with the user's favorite styles, frameworks, industries, or interests.
"""

        prompt = f"""
You are a highly precise search personalization and reranking engine.
Given the user's search query: "{query}"
{personalization_instruction}

Analyze the following list of templates and rank them from MOST relevant to LEAST relevant based on query relevance and user preferences.

Templates list:
{templates_str}

Return the results ONLY as a JSON list of the template UUID strings in order of relevance. Do not include markdown code block notation (like ```json ... ```), explanations, or comments.
Example format:
[
  "0cabb02f-7a07-4349-b1c9-b9987348bbb1",
  "d6b9d628-9774-4b53-a75d-6c178229b47e"
]
"""
        try:
            text_response = await ai_service._generate_content(
                prompt,
                response_mime_type="application/json",
                feature_name="semantic_search"
            )
            ranked_ids = robust_json_loads(text_response)
            return [uuid.UUID(rid) for rid in ranked_ids]
        except Exception as e:
            logger.error(f"RankGemini failed: {e}")

        # Fallback to the similarity search retrieved order if LLM reranking fails
        return [t["id"] for t in templates_data]

    async def keyword_search(
        self, query: str, page: int = 1, page_size: int = 20
    ) -> List[TemplateCardResponse]:
        """Full-text keyword search using PostgreSQL ILIKE."""
        filters = TemplateFilterParams(q=query, page=page, page_size=page_size)
        templates, _ = await self.template_repo.list_with_filters(filters)
        return [TemplateCardResponse.model_validate(t) for t in templates]

    async def semantic_search(
        self, query: str, limit: int = 20, category_filter: Optional[str] = None, user: Optional[User] = None
    ) -> List[TemplateCardResponse]:
        """
        Semantic search using Gemini embeddings + Qdrant similarity + RankGemini LLM Reranking.

        1. Log the search event for analytics/history collection.
        2. Embed the query with Gemini text-embedding-004 API.
        3. Compile user preferences context (if logged in).
        4. Query Qdrant for top 30 nearest matches.
        5. Re-rank top 30 matches using RankGemini, incorporating user context.
        6. Return top 10 results from PostgreSQL in ranked order.
        """
        # Step 1: Log search event for analytics/user history compilation
        await self._log_search_event(query, user)

        if not settings.GEMINI_API_KEY:
            return await self.keyword_search(query, page_size=limit)

        try:
            # Step 2: Embed the query
            query_vector = await self._get_gemini_embedding(query)

            # Compile user preferences context if user is authenticated
            user_context = None
            if user:
                user_context = await self._build_user_profile_context(user)

            # Step 3: Query Qdrant (pull top 30 for reranking)
            search_filter = None
            if category_filter:
                search_filter = qdrant_models.Filter(
                    must=[qdrant_models.FieldCondition(key="category", match=qdrant_models.MatchValue(value=category_filter))]
                )

            # Ensure collection is correctly initialized
            await self._ensure_collection()

            results = await self.qdrant.search(
                collection_name=settings.QDRANT_COLLECTION,
                query_vector=query_vector,
                limit=30,  # Grab candidate set of 30 for reranker
                query_filter=search_filter,
            )

            if not results:
                return []

            # Prepare list of candidates for RankGemini
            candidates = []
            for r in results:
                if r.payload:
                    candidates.append({
                        "id": uuid.UUID(r.payload["template_id"]),
                        "title": r.payload.get("title", ""),
                        "description": r.payload.get("description", ""),
                        "tags": r.payload.get("tags", []),
                        "industry": r.payload.get("industry", ""),
                        "style": r.payload.get("style", ""),
                        "color_scheme": r.payload.get("color_scheme", "")
                    })

            # Step 4: Re-rank using RankGemini with personalization context
            ranked_ids = await self._rank_templates(query, candidates, user_profile_context=user_context)
            # Slice to final requested limit (usually top 10)
            final_ids = ranked_ids[:limit]

            # Step 5: Fetch templates from PostgreSQL
            templates = await self.template_repo.get_by_ids(final_ids)
            id_to_template = {t.id: t for t in templates}

            return [
                TemplateCardResponse.model_validate(id_to_template[tid])
                for tid in final_ids
                if tid in id_to_template
            ]

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return await self.keyword_search(query, page_size=limit)

    async def index_template(self, template_id: uuid.UUID, text: str, metadata: dict) -> str:
        """
        Embed a template using Gemini text-embedding-004 and index it in Qdrant.
        Combines Name, Category, Industry, Description, Tags, Features, Framework, Style, and Colors.
        """
        if not settings.GEMINI_API_KEY:
            return str(template_id)

        # Build detailed document text for optimal embedding quality
        title = metadata.get("title", "")
        category = metadata.get("category", "")
        industry = metadata.get("industry", "")
        tags = metadata.get("tags", [])
        features = metadata.get("features", [])
        framework = metadata.get("framework", "")
        style = metadata.get("style", "")
        color_scheme = metadata.get("color_scheme", "")
        seo_keywords = metadata.get("seo_keywords", [])

        doc_parts = [
            f"Template Name: {title}",
            f"Category: {category}",
            f"Industry: {industry}",
            f"Description: {text}",
            f"Framework: {framework}",
            f"Style: {style}",
            f"Color Theme: {color_scheme}",
            f"Tags: {', '.join(tags)}" if tags else "",
            f"Features: {', '.join(features)}" if features else "",
            f"SEO Keywords: {', '.join(seo_keywords)}" if seo_keywords else ""
        ]
        doc_text = "\n".join([p for p in doc_parts if p])

        # Get vector embedding from Gemini
        vector = await self._get_gemini_embedding(doc_text)

        # Ensure collection is correctly initialized
        await self._ensure_collection()

        point_id = str(template_id)
        # Store metadata matching the keys parsed in RankGemini
        payload = {
            "template_id": point_id,
            "title": title,
            "category": category,
            "industry": industry,
            "description": text,
            "tags": tags,
            "features": features,
            "framework": framework,
            "style": style,
            "color_scheme": color_scheme,
            "seo_keywords": seo_keywords
        }

        await self.qdrant.upsert(
            collection_name=settings.QDRANT_COLLECTION,
            points=[qdrant_models.PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        return point_id

