"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, CheckCircle2, ImagePlus, LoaderCircle, Sparkles, WandSparkles } from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { useAppAuth } from "@/lib/auth";
import { api, API_URL } from "@/lib/api";
import "./Page.css";

const AGENTS = [
  "Planning Agent",
  "UI Designer Agent",
  "Architect Agent",
  "DB Schema Agent",
  "Backend Dev Agent",
  "Frontend Dev Agent",
  "SEO & A11y Agent",
  "Testing & Audit Agent",
  "Packaging Agent",
];

const STACK_OPTIONS = [
  { value: "react-fastapi-postgresql", title: "React + FastAPI + PostgreSQL", badge: "Emergent Standard", description: "Async FastAPI REST API, SQLAlchemy 2.0 ORM, and React 18 TypeScript frontend." },
  { value: "react-fastapi-mongodb", title: "React + FastAPI + MongoDB (FARM)", badge: "NoSQL Flexibility", description: "Emergent FARM stack: async Motor driver, MongoDB document schemas, and React UI." },
  { value: "nextjs-fastapi-postgresql", title: "Next.js 14 + FastAPI + PostgreSQL", badge: "Next.js App Router", description: "Next.js 14 App Router client with Python FastAPI backend services." },
  { value: "react-express-mongodb", title: "React + Express.js + MongoDB", badge: "MERN Stack", description: "Node.js Express REST API with Mongoose schemas and React Vite frontend." },
  { value: "nextjs-nestjs-postgresql", title: "Next.js + NestJS + PostgreSQL", badge: "TypeScript End-to-End", description: "Enterprise NestJS modules, TypeORM entities, and Next.js frontend." },
  { value: "html-css-js", title: "Static Website (HTML5 / CSS / JS)", badge: "Lightweight", description: "Zero-dependency static site with semantic HTML, custom CSS, and vanilla JS." },
];

export default function StudioPage() {
  const navigate = useNavigate();
  const { getToken } = useAppAuth();
  const [categories, setCategories] = useState([]);
  const [categoryId, setCategoryId] = useState("");
  const [genre, setGenre] = useState("");
  const [pageStructure, setPageStructure] = useState("");
  const [stack, setStack] = useState("react-fastapi-postgresql");
  const [prompt, setPrompt] = useState("");
  const [plan, setPlan] = useState(null);
  const [buildPrompt, setBuildPrompt] = useState("");
  const [loadingBuildPrompt, setLoadingBuildPrompt] = useState(false);
  const [answers, setAnswers] = useState({});
  const [completedQuestions, setCompletedQuestions] = useState([]);
  const [skippedQuestions, setSkippedQuestions] = useState([]);
  const [uploadedAssets, setUploadedAssets] = useState([]);
  const [uploadingImages, setUploadingImages] = useState(false);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [events, setEvents] = useState([]);
  const [activeAgent, setActiveAgent] = useState("");
  const generationInFlight = useRef(false);
  const buildSessionId = useRef("");

  useEffect(() => {
    let alive = true;
    getToken().then((token) => api.get("/categories", token)).then((data) => {
      if (alive) setCategories(Array.isArray(data) ? data : []);
    }).catch(() => {});
    return () => { alive = false; };
  }, []); // Auth is loaded before the protected Studio route mounts.

  const selectedCategory = useMemo(() => categories.find((item) => item.id === categoryId), [categories, categoryId]);
  const selectedSiteType = `${selectedCategory?.name || ""} ${genre}`;
  const constructionPattern = /construction|contractor|building company|roofing|remodel(?:ing)?|renovation|home improvement|(?:home|house|custom|commercial|residential) builder/i;
  const portfolioPattern = /\bportfolio\b|\bresume\b|résumé|\bcv\b|personal\s+(?:site|website)\b|photographer\s+portfolio/i;
  const promptHasProjectType = /construction|contractor|building company|roofing|remodel|renovation|home improvement|builder|portfolio|resume|résumé|\bcv\b|photographer|restaurant|cafe|coffee|\btea\b|bakery|food|dining|shop|store|e-?commerce|real estate|property|realtor|event|conference|festival|wedding|school|education|course|training|academy|university|health|clinic|medical|dental|wellness|therapy|hotel|travel|tour|hospitality|salon|beauty|fitness|gym|agency|consulting|software|saas|\bapp\b|blog|publication|nonprofit|charity/i.test(prompt);
  const isConstructionRequest = constructionPattern.test(prompt) || (!promptHasProjectType && constructionPattern.test(selectedSiteType));
  const isPortfolioRequest = !isConstructionRequest && (portfolioPattern.test(prompt) || (!promptHasProjectType && portfolioPattern.test(selectedSiteType)));
  const siteImageContext = promptHasProjectType ? prompt : `${selectedSiteType} ${prompt}`;
  const effectivePageStructure = pageStructure || (isPortfolioRequest ? "single_page" : isConstructionRequest ? "multi_page" : "");

  async function buildPlan(event) {
    event.preventDefault();
    setError("");
    setLoadingPlan(true);
    try {
      const token = await getToken();
      const result = await api.post("/studio/plan", {
        prompt,
        category: selectedCategory?.name || "Website",
        genre: genre.trim() || selectedCategory?.name || "Website",
        page_structure: effectivePageStructure,
        stack: stack || "react-fastapi-postgresql",
      }, token);
      setPlan({
        ...result.plan,
        pages: (result.plan.pages || []).map((page) => ({
          ...page,
          included: true,
          selected_sections: [...(page.sections || [])],
        })),
      });
      setAnswers({});
      setCompletedQuestions([]);
      setSkippedQuestions([]);
      setBuildPrompt("");
    } catch (err) {
      setError(err.message || "The Planning Agent could not create a plan.");
    } finally {
      setLoadingPlan(false);
    }
  }

  async function createBuildPrompt() {
    setLoadingBuildPrompt(true);
    setError("");
    try {
      const token = await getToken();
      const result = await api.post("/studio/prompt", {
        prompt,
        category: selectedCategory?.name || "Website",
        genre: genre.trim() || selectedCategory?.name || "Website",
        page_structure: plan?.architecture_type || effectivePageStructure,
        plan,
        answers,
        image_urls: [],
        image_assets: uploadedAssets,
        stack: stack || "react-fastapi-postgresql",
      }, token);
      setBuildPrompt(result.build_prompt || "");
    } catch (err) {
      setError(err.message || "The Planning Agent could not create the editable build prompt.");
    } finally {
      setLoadingBuildPrompt(false);
    }
  }

  async function startGeneration() {
    if (generationInFlight.current) return;
    generationInFlight.current = true;
    setError("");
    setEvents([]);
    setActiveAgent(AGENTS[0]);
    buildSessionId.current = "";
    setGenerating(true);
    try {
      const token = await getToken();
      const response = await fetch(`${API_URL}/studio/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          prompt,
          category_id: categoryId,
          category: selectedCategory?.name || "Website",
          genre: genre.trim() || selectedCategory?.name || "Website",
          build_prompt: buildPrompt,
          plan,
          answers,
          image_urls: [],
          image_assets: uploadedAssets,
          stack: stack || "react-fastapi-postgresql",
        }),
      });
      if (!response.ok || !response.body) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Could not start website generation.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        const frames = buffer.split("\n\n");
        buffer = frames.pop() || "";
        for (const frame of frames) {
          const line = frame.split("\n").find((part) => part.startsWith("data: "));
          if (!line) continue;
          const item = JSON.parse(line.slice(6));
          if (item.type === "error") throw new Error(item.message || "Studio generation failed.");
          if (item.type === "session") buildSessionId.current = item.build_id || "";
          if (item.type === "agent") {
            setActiveAgent(item.agent);
            setEvents((current) => [...current, { ...item, key: `${item.agent}-${item.status}-${current.length}` }]);
          } else if (item.type === "page") {
            setActiveAgent("Frontend Dev Agent");
            setEvents((current) => [...current, { ...item, key: `${item.filename}-${item.status}-${current.length}` }]);
          } else if (item.type === "model") {
            setEvents((current) => [...current, { ...item, key: `${item.page}-${item.provider}-${current.length}` }]);
          } else if (item.type === "complete") {
            const buildQuery = buildSessionId.current ? `&build=${encodeURIComponent(buildSessionId.current)}` : "";
            navigate(`/preview?template=${encodeURIComponent(item.project.id)}&mode=live${buildQuery}`, { replace: true });
            return;
          }
        }
      }
    } catch (err) {
      setError(err.message || "Studio generation failed. Your plan and answers are still here.");
    } finally {
      generationInFlight.current = false;
      setGenerating(false);
    }
  }

  async function uploadPortfolioImages(role, fileList) {
    const files = Array.from(fileList || []).filter((file) => file.type.startsWith("image/"));
    if (!files.length) return;
    setUploadingImages(true);
    setError("");
    try {
      const token = await getToken();
      const remaining = Math.max(0, 16 - uploadedAssets.length);
      for (const file of files.slice(0, remaining)) {
        const form = new FormData();
        form.append("file", file);
        const response = await fetch(`${API_URL}/files/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok || !result.url) throw new Error(result.detail || `Could not upload ${file.name}.`);
        setUploadedAssets((current) => [...current, { role, url: result.url, alt: file.name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ") }]);
        setBuildPrompt("");
      }
    } catch (err) {
      setError(err.message || "Image upload failed.");
    } finally {
      setUploadingImages(false);
    }
  }

  function updateAnswer(id, value) {
    setAnswers((current) => ({ ...current, [id]: value }));
    setBuildPrompt("");
  }

  function submitClarification(question, index) {
    const id = question.id || `q-${index}`;
    const value = String(answers[id] || "").trim();
    if (!value && question.required) return;
    if (value) setCompletedQuestions((current) => [...new Set([...current, id])]);
    else setSkippedQuestions((current) => [...new Set([...current, id])]);
  }

  function togglePlanPage(filename) {
    setBuildPrompt("");
    setPlan((current) => ({
      ...current,
      pages: current.pages.map((page) => page.filename === filename && !page.required
        ? { ...page, included: page.included === false }
        : page),
    }));
  }

  function togglePageSection(filename, section) {
    setBuildPrompt("");
    setPlan((current) => ({
      ...current,
      pages: current.pages.map((page) => {
        if (page.filename !== filename) return page;
        const selected = page.selected_sections || page.sections || [];
        if (selected.includes(section) && selected.length <= 1) return page;
        return {
          ...page,
          selected_sections: selected.includes(section)
            ? selected.filter((item) => item !== section)
            : [...selected, section],
        };
      }),
    }));
  }

  const selectedPageCount = plan?.pages?.filter((page) => page.included !== false || page.required).length || 0;
  const clarificationQuestions = plan?.questions || [];
  const activeClarificationIndex = clarificationQuestions.findIndex((question, index) => {
    const id = question.id || `q-${index}`;
    return !completedQuestions.includes(id) && !skippedQuestions.includes(id);
  });
  const clarificationsComplete = activeClarificationIndex < 0;

  const palette = plan?.design_system || {};
  const safeColor = (value, fallback) => /^#[0-9a-f]{6}$/i.test(String(value || "")) ? value : fallback;
  const previewImage = uploadedAssets[0]?.url;
  const uploadFields = plan?.image_uploads?.length ? plan.image_uploads : isPortfolioRequest
    ? [
        { role: "portrait", label: "Portrait", hint: "Your profile photo or headshot", multiple: false },
        { role: "skills", label: "Skills & tools", hint: "Logos for your skills or tools", multiple: true },
        { role: "project", label: "Projects", hint: "Screenshots or photos of your work", multiple: true },
      ]
    : isConstructionRequest
      ? [
          { role: "project", label: "Completed projects", hint: "Real site photos or project images", multiple: true },
          { role: "team", label: "Team", hint: "Your real crew or team photos", multiple: true },
          { role: "equipment", label: "Equipment & work sites", hint: "Your equipment or active job-site photos", multiple: true },
        ]
      : /\btea\b/i.test(siteImageContext)
      ? [
          { role: "general", label: "Tea brand & menu images", hint: "Logo, tea varieties, drinks, ingredients, packaging, or menu photos", multiple: true },
          { role: "project", label: "Tea preparation & location", hint: "Your real tea service, storefront, garden, or customer experience", multiple: true },
        ]
      : /cafe|coffee|restaurant|bakery|food|dining|menu/i.test(siteImageContext)
      ? [
          { role: "general", label: "Restaurant brand & menu", hint: "Logo, signature dishes, drinks, ingredients, or menu photos", multiple: true },
          { role: "project", label: "Dining space & experience", hint: "Your real storefront, interior, kitchen, or dining experience", multiple: true },
        ]
      : /real estate|property|realtor|estate agent/i.test(siteImageContext)
      ? [
          { role: "general", label: "Agency branding", hint: "Logo and agent or office images", multiple: true },
          { role: "project", label: "Property listings", hint: "Real homes, developments, and listing images", multiple: true },
        ]
      : /event|conference|festival|wedding/i.test(siteImageContext)
      ? [
          { role: "general", label: "Event identity", hint: "Event logo, theme, and promotional imagery", multiple: true },
          { role: "project", label: "Venue & program", hint: "Venue, speakers, performers, or past event photos", multiple: true },
        ]
      : /school|education|course|training|academy|university/i.test(siteImageContext)
      ? [
          { role: "general", label: "School or program branding", hint: "Logo and learning materials", multiple: true },
          { role: "project", label: "Campus & learning", hint: "Real classrooms, courses, and student activities", multiple: true },
        ]
      : /health|clinic|medical|dental|wellness|therapy/i.test(siteImageContext)
      ? [
          { role: "general", label: "Practice branding & care", hint: "Logo, clinic, equipment, or published care information", multiple: true },
          { role: "team", label: "Practitioner & facility photos", hint: "Real staff and spaces, with permission to publish", multiple: true },
        ]
      : /hotel|travel|tour|hospitality|accommodation/i.test(siteImageContext)
      ? [
          { role: "general", label: "Property or tour identity", hint: "Logo, destination, and experience imagery", multiple: true },
          { role: "project", label: "Rooms, places & experiences", hint: "Real rooms, destinations, tours, or amenities", multiple: true },
        ]
      : /software|saas|\bapp\b|technology|digital product/i.test(siteImageContext)
      ? [
          { role: "general", label: "Product & brand assets", hint: "Logo, product interface, app screens, or feature visuals", multiple: true },
          { role: "project", label: "Screenshots & workflows", hint: "Real product screens, dashboards, or workflow examples", multiple: true },
        ]
      : /salon|beauty|spa|barber|skincare/i.test(siteImageContext)
      ? [
          { role: "general", label: "Beauty brand & services", hint: "Logo, products, treatments, or service imagery", multiple: true },
          { role: "project", label: "Space & results", hint: "Your real salon, studio, or work examples with permission", multiple: true },
        ]
      : /fitness|gym|sports|yoga|personal trainer/i.test(siteImageContext)
      ? [
          { role: "general", label: "Fitness brand & programs", hint: "Logo, classes, equipment, or training programs", multiple: true },
          { role: "project", label: "Studio & activities", hint: "Your real facility, classes, or events", multiple: true },
        ]
      : /architecture|architect|interior design|landscape design/i.test(siteImageContext)
      ? [
          { role: "general", label: "Studio & design identity", hint: "Logo, studio, plans, or material samples", multiple: true },
          { role: "project", label: "Spaces & completed work", hint: "Real buildings, interiors, landscapes, or project renders", multiple: true },
        ]
      : [
          { role: "general", label: `${genre || selectedCategory?.name || "Project"} brand & key images`, hint: "Logo, products, location, or key visuals relevant to this project", multiple: true },
          { role: "project", label: `${genre || selectedCategory?.name || "Project"} photos & examples`, hint: "Real work, services, spaces, or examples relevant to this project", multiple: true },
        ];

  return (
    <div className="studio-app min-h-screen bg-[#080b12] text-slate-100">
      <Navbar />
      <main className="studio-main mx-auto max-w-6xl px-4 pb-20 pt-28 sm:px-6">
        <button onClick={() => navigate("/marketplace")} className="studio-back mb-7 inline-flex items-center gap-2 text-sm text-slate-400 transition hover:text-white">
          <ArrowLeft size={16} /> Back to marketplace
        </button>

        <div className="studio-intro mb-10">
          <div className="studio-intro-copy">
            <div className="studio-eyebrow"><Sparkles size={14} /> YOUR PRIVATE AI WEBSITE STUDIO</div>
            <h1>From a rough idea<br /><span>to a complete website.</span></h1>
            <p>Shape the plan, choose your stack, and let nine focused agents build your full-stack application and API.</p>
          </div>
          <div className="studio-agent-preview" aria-label="Studio workflow">
            <span className="studio-agent-orbit"><Sparkles size={22} /></span>
            <span className="studio-agent-caption">YOUR BUILD TEAM</span>
            <strong>Nine agents.<br />One finished site.</strong>
            <div className="studio-agent-dots">{AGENTS.map((agent, index) => <i key={agent} title={agent} className={index === 0 ? "active" : ""} />)}</div>
            <small>Plan · Architect · Database · Backend · Frontend · Review</small>
          </div>
        </div>

        {!plan ? (
          <form onSubmit={buildPlan} className="grid gap-5 rounded-3xl border border-white/10 bg-white/[0.035] p-5 shadow-2xl shadow-black/20 sm:p-8">
            <div>
              <label className="mb-2 block text-sm font-semibold text-slate-200">What kind of website do you want?</label>
              <textarea required minLength={10} maxLength={100000} value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={6} placeholder="Describe the site, who it is for, what visitors should do, and any style you have in mind…" className="w-full resize-y rounded-2xl border border-white/10 bg-[#0c111b] px-4 py-3 text-sm leading-6 text-white outline-none transition placeholder:text-slate-600 focus:border-violet-400/60" />
              <div className="mt-1 text-right text-xs text-slate-600">{prompt.length.toLocaleString()}/100,000</div>
            </div>
            <fieldset>
              <legend className="mb-2 block text-sm font-semibold text-slate-200">How many pages should your website have?</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                {[
                  { value: "single_page", title: "Single page", description: "One scrolling page with all content and sections." },
                  { value: "multi_page", title: "Multiple pages", description: "Separate pages for the main parts of your website." },
                ].map((option) => (
                  <label key={option.value} className={`cursor-pointer rounded-2xl border p-4 transition ${pageStructure === option.value ? "border-violet-400 bg-violet-400/10" : "border-white/10 bg-[#0c111b] hover:border-white/20"}`}>
                    <input className="sr-only" type="radio" name="page-structure" value={option.value} checked={effectivePageStructure === option.value} onChange={() => setPageStructure(option.value)} required />
                    <span className="block text-sm font-semibold text-white">{option.title}</span>
                    <span className="mt-1 block text-xs leading-5 text-slate-400">{option.description}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <div className="mb-2 flex items-center justify-between">
                <legend className="text-sm font-semibold text-slate-200">Architecture &amp; Tech Stack</legend>
                <span className="rounded-full bg-violet-400/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-violet-300">Emergent Multi-Agent</span>
              </div>
              <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                {STACK_OPTIONS.map((opt) => (
                  <label key={opt.value} className={`cursor-pointer rounded-2xl border p-3.5 transition ${stack === opt.value ? "border-violet-400 bg-violet-400/10 shadow-lg shadow-violet-500/10" : "border-white/10 bg-[#0c111b] hover:border-white/20"}`}>
                    <input className="sr-only" type="radio" name="tech-stack" value={opt.value} checked={stack === opt.value} onChange={() => setStack(opt.value)} />
                    <div className="flex items-center justify-between gap-1">
                      <span className="block text-xs font-bold text-white">{opt.title}</span>
                      <span className="shrink-0 rounded bg-white/5 px-1.5 py-0.5 text-[9px] font-semibold text-violet-300">{opt.badge}</span>
                    </div>
                    <span className="mt-1.5 block text-[11px] leading-4 text-slate-400">{opt.description}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-semibold text-slate-200">Marketplace category</label>
                <select required value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className="w-full rounded-xl border border-white/10 bg-[#0c111b] px-4 py-3 text-sm text-white outline-none focus:border-violet-400/60">
                  <option value="">Choose a category</option>
                  {categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
              </div>
              <div>
                <label className="mb-2 block text-sm font-semibold text-slate-200">Genre or site type</label>
                <input value={genre} onChange={(e) => setGenre(e.target.value)} maxLength={100} placeholder="Portfolio, online shop, restaurant…" className="w-full rounded-xl border border-white/10 bg-[#0c111b] px-4 py-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-violet-400/60" />
              </div>
            </div>
            {error && <p role="alert" className="rounded-xl border border-rose-400/20 bg-rose-400/10 px-4 py-3 text-sm text-rose-200">{error}</p>}
            <button disabled={loadingPlan || !categoryId || !effectivePageStructure || prompt.trim().length < 10} className="inline-flex w-fit items-center justify-center gap-2 rounded-xl bg-violet-500 px-5 py-3 text-sm font-bold text-white transition hover:bg-violet-400 disabled:cursor-not-allowed disabled:opacity-50">
              {loadingPlan ? <LoaderCircle size={17} className="animate-spin" /> : <WandSparkles size={17} />}
              {loadingPlan ? "Planning your site…" : "Plan my website"}
              {!loadingPlan && <ArrowRight size={16} />}
            </button>
          </form>
        ) : (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.45fr)_minmax(300px,0.75fr)]">
            <section className="space-y-6">
              <div className="rounded-3xl border border-white/10 bg-white/[0.035] p-5 sm:p-7">
                <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
                  <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-300">Planning Agent · Proposal</p><h2 className="mt-2 text-2xl font-bold">{plan.title}</h2><p className="mt-2 text-sm leading-6 text-slate-400">{plan.summary}</p></div>
                  <span className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300">{selectedPageCount} of {plan.pages.length} pages · {selectedPageCount === 1 ? "single page" : "multi page"}</span>
                </div>
                <div className="mb-4 flex items-center justify-between gap-3 border-b border-white/10 pb-3">
                  <div><h3 className="text-sm font-bold">Required pages &amp; page parts</h3><p className="mt-1 text-xs text-slate-500">Home is required. Choose the other pages and the sections each page needs.</p></div>
                  <span className="shrink-0 rounded-full bg-violet-400/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-violet-200">{selectedPageCount} selected</span>
                </div>
                <div className="space-y-3">
                  {plan.pages.map((page, index) => (
                    <article key={page.filename} className={`rounded-2xl border bg-[#0c111b] p-4 ${page.included === false ? "border-white/5 opacity-60" : "border-white/10"}`}>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <label className="flex cursor-pointer items-center gap-3">
                          <input type="checkbox" checked={page.included !== false || page.required} disabled={!!page.required} onChange={() => togglePlanPage(page.filename)} className="h-4 w-4 accent-violet-400 disabled:cursor-not-allowed" aria-label={`${page.required ? "Required" : "Include"} ${page.name} page`} />
                          <span className="font-semibold">{String(index + 1).padStart(2, "0")} · {page.name}</span>
                        </label>
                        <div className="flex items-center gap-2"><span className={`rounded-full px-2 py-1 text-[9px] font-bold uppercase tracking-wider ${page.required ? "bg-amber-300/10 text-amber-200" : "bg-white/5 text-slate-500"}`}>{page.required ? "Required" : page.included === false ? "Excluded" : "Optional"}</span><code className="text-xs text-violet-200">{page.filename}</code></div>
                      </div>
                      <p className="mt-2 text-sm text-slate-400">{page.purpose}</p>
                      {!!page.sections?.length && <div className="mt-3"><p className="mb-2 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Page parts</p><div className="flex flex-wrap gap-2">{page.sections.map((section) => {
                        const selected = (page.selected_sections || page.sections).includes(section);
                        return <button key={section} type="button" disabled={page.included === false} aria-pressed={selected} onClick={() => togglePageSection(page.filename, section)} className={`rounded-lg border px-2.5 py-1.5 text-xs transition ${selected ? "border-violet-400/40 bg-violet-400/10 text-violet-100" : "border-white/10 bg-transparent text-slate-500 hover:text-slate-300"} disabled:cursor-not-allowed disabled:opacity-40`}>{selected ? "✓ " : "+ "}{section}</button>;
                      })}</div></div>}
                      {page.primary_action && <p className="mt-2 text-xs text-slate-400">Primary action: <span className="text-slate-200">{page.primary_action}</span></p>}
                    </article>
                  ))}
                </div>
                {plan.design_direction && <div className="mt-5 rounded-2xl border border-violet-400/15 bg-violet-400/[0.06] p-4"><h3 className="text-sm font-semibold text-violet-200">Creative direction</h3><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">{plan.design_direction}</p></div>}
              </div>

              <div className="rounded-3xl border border-white/10 bg-white/[0.035] p-5 sm:p-7">
                <div className="mb-4"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-300">UI Designer Agent · Visual concept</p><h2 className="mt-2 text-xl font-bold">A preview of the direction</h2><p className="mt-1 text-sm text-slate-400">This concept reflects the planned palette, layout, and imagery. Answer the Studio’s questions one at a time, then it will build the pages in sequence.</p></div>
                <div className="overflow-hidden rounded-2xl border border-black/10 shadow-xl" style={{ backgroundColor: safeColor(palette.background, "#f3f4f6"), color: safeColor(palette.text, "#172033") }}>
                  <div className="flex items-center justify-between border-b border-black/10 px-4 py-3 text-xs">
                    <strong>{plan.title}</strong>
                    <div className="hidden gap-4 sm:flex">{plan.pages.filter((page) => page.included !== false || page.required).slice(0, 3).map((page) => <span key={page.filename} className="opacity-70">{page.name}</span>)}</div>
                  </div>
                  <div className="grid min-h-[250px] items-center gap-5 p-5 sm:grid-cols-[1.05fr_0.95fr] sm:p-8">
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-[0.2em]" style={{ color: safeColor(palette.primary, "#6d4aff") }}>{genre || selectedCategory?.name || "Website"}</span>
                      <h3 className="mt-3 text-3xl font-black leading-tight sm:text-4xl">{plan.preview?.headline || plan.title}</h3>
                      <p className="mt-3 max-w-md text-sm leading-6 opacity-70">{plan.preview?.subheadline || plan.summary}</p>
                      <span className="mt-5 inline-flex rounded-lg px-4 py-2 text-xs font-bold text-white" style={{ backgroundColor: safeColor(palette.primary, "#6d4aff") }}>{plan.preview?.primary_action || "Explore"}</span>
                    </div>
                    <div className="relative min-h-[160px] overflow-hidden rounded-2xl" style={{ background: `linear-gradient(135deg, ${safeColor(palette.primary, "#6d4aff")}55, ${safeColor(palette.accent, "#f28a64")}66)` }}>
                      {previewImage && <img src={previewImage} alt="Selected visual direction" className="absolute inset-0 h-full w-full object-cover" />}
                      <div className="absolute inset-0" style={{ background: `linear-gradient(135deg, ${safeColor(palette.primary, "#6d4aff")}55, transparent 75%)` }} />
                      <div className="absolute bottom-3 left-3 rounded-lg px-3 py-2 text-[10px] font-semibold text-white backdrop-blur" style={{ backgroundColor: `${safeColor(palette.surface, "#ffffff")}44` }}>{palette.image_treatment || "Image-led visual story"}</div>
                    </div>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-400">
                  {[palette.heading_font, palette.body_font, palette.hero_layout].filter(Boolean).map((item) => <span key={item} className="rounded-full border border-white/10 px-2.5 py-1">{item}</span>)}
                </div>
              </div>

              <div className="rounded-3xl border border-white/10 bg-white/[0.035] p-5 sm:p-7">
                <div className="mb-5"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-300">Build chat · one question at a time</p><h2 className="mt-2 text-xl font-bold">Let’s get the details right</h2><p className="mt-1 text-sm leading-6 text-slate-400">I’ll ask only what the plan still needs. Your answers shape the site and its pages.</p></div>
                <div className="space-y-3">
                  {(plan.questions || []).map((question, index) => {
                    const id = question.id || `q-${index}`;
                    const wasAnswered = completedQuestions.includes(id);
                    const wasSkipped = skippedQuestions.includes(id);
                    if (!wasAnswered && !wasSkipped) return null;
                    return <div key={id} className="space-y-2">
                      <div className="max-w-[88%] rounded-2xl rounded-bl-sm border border-white/10 bg-[#0c111b] px-4 py-3 text-sm text-slate-300">{question.question}</div>
                      <div className="ml-auto max-w-[88%] rounded-2xl rounded-br-sm bg-violet-500/15 px-4 py-3 text-sm text-violet-100">{wasSkipped ? "Skip for now" : answers[id]}</div>
                    </div>;
                  })}
                  {activeClarificationIndex >= 0 ? (() => {
                    const question = clarificationQuestions[activeClarificationIndex];
                    const id = question.id || `q-${activeClarificationIndex}`;
                    const value = answers[id] || "";
                    return <div className="space-y-3 pt-2" key={id}>
                      <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-[0.16em] text-violet-300"><span>Studio asks</span><span>{completedQuestions.length + skippedQuestions.length + 1} / {clarificationQuestions.length}</span></div>
                      <label htmlFor={`active-${id}`} className="block rounded-2xl rounded-bl-sm border border-violet-400/20 bg-violet-400/[0.07] px-4 py-3 text-sm leading-6 text-slate-100">{question.question}{question.required && <span className="ml-1 text-violet-300">*</span>}</label>
                      {question.input_type === "select" ? <select id={`active-${id}`} value={value} onChange={(event) => updateAnswer(id, event.target.value)} className="w-full border border-white/10 bg-[#0c111b] px-4 py-3 text-sm text-white"><option value="">Choose an answer</option>{(question.options || []).map((option) => <option key={option} value={option}>{option}</option>)}</select> : question.input_type === "textarea" ? <textarea id={`active-${id}`} value={value} onChange={(event) => updateAnswer(id, event.target.value)} placeholder={question.placeholder || "Type your answer…"} rows={3} className="w-full border border-white/10 bg-[#0c111b] px-4 py-3 text-sm text-white placeholder:text-slate-600" /> : <input id={`active-${id}`} value={value} onChange={(event) => updateAnswer(id, event.target.value)} placeholder={question.placeholder || "Type your answer…"} className="w-full border border-white/10 bg-[#0c111b] px-4 py-3 text-sm text-white placeholder:text-slate-600" />}
                      <div className="flex justify-end gap-2">
                        {!question.required && <button type="button" onClick={() => submitClarification(question, activeClarificationIndex)} className="rounded-xl border border-white/10 px-4 py-2.5 text-sm text-slate-300">Skip</button>}
                        <button type="button" onClick={() => submitClarification(question, activeClarificationIndex)} disabled={!value.trim()} className="inline-flex items-center gap-2 rounded-xl bg-violet-500 px-4 py-2.5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-40">Send answer <ArrowRight size={15} /></button>
                      </div>
                    </div>;
                  })() : <p className="rounded-xl border border-emerald-400/15 bg-emerald-400/[0.06] px-4 py-3 text-sm text-emerald-200">That’s everything I need. Next I’ll build the pages in order, then open your live preview so you can keep editing by chat.</p>}
                </div>
              </div>
            </section>

            <aside className="space-y-6">
              <div className="rounded-3xl border border-white/10 bg-white/[0.035] p-5 sm:p-6">
                <div className="flex items-center gap-2"><ImagePlus size={18} className="text-violet-300" /><h2 className="font-bold">Choose images</h2></div>
                <p className="mt-2 text-sm leading-6 text-slate-400">Upload up to 16 images that match this project. No image links are needed: if you leave this empty, Studio automatically selects relevant illustrative stock photos.</p>
                <div className="mt-4 space-y-3">
                  {uploadFields.map((field) => (
                    <label key={`${field.role}-${field.label}`} className="block rounded-xl border border-white/10 bg-[#0c111b] p-3">
                      <span className="block text-xs font-semibold text-slate-200">{field.label}</span>
                      <span className="mt-1 block text-[11px] text-slate-500">{field.hint}</span>
                      <input className="mt-2 block w-full text-xs text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-violet-500/15 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-violet-200" type="file" accept="image/*" multiple={field.multiple} disabled={uploadingImages || uploadedAssets.length >= 16} onChange={(event) => { uploadPortfolioImages(field.role, event.target.files); event.target.value = ""; }} />
                    </label>
                  ))}
                </div>
                {uploadedAssets.length > 0 && <div className="mt-3 space-y-2">{uploadedAssets.map((asset, index) => <div key={`${asset.url}-${index}`} className="flex items-center justify-between gap-2 rounded-lg bg-white/5 px-3 py-2 text-xs text-slate-300"><span className="truncate">{asset.alt} · {asset.role}</span><button type="button" onClick={() => { setUploadedAssets((current) => current.filter((_, itemIndex) => itemIndex !== index)); setBuildPrompt(""); }} className="text-slate-500 hover:text-white" aria-label={`Remove ${asset.alt}`}>Remove</button></div>)}</div>}
                {uploadingImages && <p className="mt-2 text-xs text-violet-200">Uploading images…</p>}
              </div>

              {generating ? (
                <div className="rounded-3xl border border-violet-400/20 bg-violet-400/[0.06] p-5 sm:p-6">
                  <div className="flex items-center gap-3"><LoaderCircle size={18} className="animate-spin text-violet-300" /><div><p className="text-xs uppercase tracking-widest text-violet-300">Working now</p><p className="mt-1 font-bold">{activeAgent}</p></div></div>
                  <div className="mt-5 space-y-3">
                    {AGENTS.map((name) => {
                      const done = events.some((event) => event.agent === name && event.status === "completed");
                      const active = activeAgent === name;
                      return <div key={name} className={`flex items-center gap-2 text-sm ${done ? "text-emerald-300" : active ? "text-white" : "text-slate-600"}`}>{done ? <CheckCircle2 size={15} /> : active ? <LoaderCircle size={15} className="animate-spin" /> : <span className="h-3.5 w-3.5 rounded-full border border-current" />}{name}</div>;
                    })}
                  </div>
                  <div className="mt-5 max-h-48 space-y-2 overflow-auto border-t border-white/10 pt-4">
                    {events.slice(-10).map((event) => (
                      <p key={event.key} className="text-xs leading-5 text-slate-400">
                        {event.type === "page"
                          ? `${event.status === "completed" ? "✓" : "•"} ${event.name}${event.index && event.total ? ` (${event.index}/${event.total})` : ""}`
                          : event.type === "model"
                            ? `Code model · ${event.page}: ${event.provider} / ${event.model}`
                            : `${event.status === "completed" ? "✓" : "•"} ${event.agent}: ${event.detail}`}
                      </p>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="rounded-3xl border border-white/10 bg-white/[0.035] p-5 sm:p-6">
                  <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-violet-300">Step 3 · Generate &amp; review</p>
                  <h2 className="mt-1 font-bold">Your editable project prompt</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-400">Click below to create the prompt. It will appear here as an editable chat message before the agents generate any code.</p>
                  {error && <p role="alert" className="mt-3 rounded-xl border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-xs text-rose-200">{error}</p>}
                  {!buildPrompt ? (
                    <>
                      {!clarificationsComplete && <p className="mt-3 rounded-xl border border-amber-300/15 bg-amber-300/5 px-3 py-2 text-xs leading-5 text-amber-100/80">Finish the one-at-a-time questions before building the site.</p>}
                      {uploadingImages && <p className="mt-3 text-xs text-violet-200">Wait for image uploads to finish before creating the prompt.</p>}
                      <button onClick={createBuildPrompt} disabled={!categoryId || !clarificationsComplete || uploadingImages || loadingBuildPrompt} className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-violet-500 px-4 py-3 text-sm font-bold text-white transition hover:bg-violet-400 disabled:opacity-50">
                      {loadingBuildPrompt ? <LoaderCircle size={16} className="animate-spin" /> : <WandSparkles size={16} />}
                      {loadingBuildPrompt ? "Writing your project prompt…" : "Create my editable prompt"}
                      </button>
                    </>
                  ) : (
                    <div className="mt-5 space-y-3">
                      <div className="flex justify-end"><div className="max-w-[90%] rounded-2xl rounded-br-md bg-violet-500/15 px-3 py-2.5 text-xs leading-5 text-violet-100"><span className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-violet-300">Your request</span>{prompt}</div></div>
                      <div className="rounded-2xl rounded-tl-md border border-white/10 bg-[#0c111b] p-3">
                        <label htmlFor="approved-build-prompt" className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-emerald-300">Planning Agent · Editable build prompt</label>
                        <textarea id="approved-build-prompt" value={buildPrompt} maxLength={60000} onChange={(event) => setBuildPrompt(event.target.value)} rows={18} className="w-full resize-y rounded-xl border border-white/10 bg-[#080b12] px-3 py-3 font-mono text-xs leading-5 text-slate-200 outline-none focus:border-violet-400/50" aria-label="Edit the full website build prompt" />
                        <div className="mt-1 text-right text-[10px] text-slate-600">{buildPrompt.length.toLocaleString()}/60,000</div>
                      </div>
                      <button onClick={createBuildPrompt} disabled={loadingBuildPrompt || !clarificationsComplete || uploadingImages} className="w-full rounded-xl border border-white/10 px-3 py-2.5 text-xs font-semibold text-slate-300 transition hover:bg-white/5 disabled:opacity-50">{loadingBuildPrompt ? "Regenerating…" : "Refresh build brief from chat"}</button>
                      <button onClick={startGeneration} disabled={buildPrompt.trim().length < 100 || !clarificationsComplete || uploadingImages} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-violet-500 px-4 py-3 text-sm font-bold text-white transition hover:bg-violet-400 disabled:opacity-50"><WandSparkles size={16} /> Build my website</button>
                      <p className="text-center text-[11px] text-slate-500">Studio generates and reviews each page in sequence. When it’s ready, you can refine the live site by chatting with the editor.</p>
                    </div>
                  )}
                  <button onClick={() => { setPlan(null); setBuildPrompt(""); setError(""); }} className="mt-3 w-full rounded-xl border border-white/10 px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:bg-white/5">Edit brief and plan</button>
                </div>
              )}
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}
