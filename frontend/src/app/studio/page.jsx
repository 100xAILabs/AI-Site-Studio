"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, ImagePlus, LoaderCircle, Sparkles, WandSparkles, Trash2, Layers, Tag, Eye, Brain, Check, FileText, Cpu } from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import { useAppAuth } from "@/lib/auth";
import { api, API_URL } from "@/lib/api";
import { useStudioBuildStore } from "@/store/studioBuildStore";
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

export default function StudioPage() {
  const navigate = useNavigate();
  const { getToken } = useAppAuth();
  const [categories, setCategories] = useState([]);
  const [categoryId, setCategoryId] = useState("");
  const [genre, setGenre] = useState("");
  const [pageStructure, setPageStructure] = useState("");
  const [prompt, setPrompt] = useState("");
  const [plan, setPlan] = useState(null);
  const [currentStep, setCurrentStep] = useState(1);
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

  const buildStore = useStudioBuildStore();
  const isGenerating = buildStore.isBuilding || generating;
  const currentActiveAgent = buildStore.activeAgent || activeAgent;
  const currentEvents = buildStore.events?.length ? buildStore.events : events;

  const autoDetectedStack = useMemo(() => {
    const categoryName = (categories.find((c) => String(c.id) === String(categoryId))?.name || "").toLowerCase();
    const catSlug = (categories.find((c) => String(c.id) === String(categoryId))?.slug || "").toLowerCase();
    const genreLower = (genre || "").toLowerCase();
    const promptLower = (prompt || "").toLowerCase();

    // 1. Static HTML showcase categories (marketing, company, portfolio, brochure, presentation)
    const htmlCategories = [
      "portfolio", "personal", "resume", "cv", "showcase", "photography",
      "artist", "restaurant", "cafe", "food", "menu", "bakery", "event",
      "wedding", "conference", "landing page", "one page", "brochure",
      "coming soon", "creative", "blog", "business", "company", "agency",
      "corporate", "consulting", "services", "profile", "brochure website",
    ];
    const isHtmlCat = htmlCategories.some((c) => categoryName.includes(c) || catSlug.includes(c) || genreLower.includes(c));

    // 2. Portfolio, showcase, or company informational request in prompt
    const isShowcaseOrPortfolio = /\b(?:portfolio|resume|résumé|cv|curriculum\s+vitae|personal\s+(?:site|website)|developer\s+portfolio|designer\s+portfolio|freelancer\s+portfolio|photographer|showcase\s+my\s+work|showcase\s+our\s+work|show\s+what\s+we\s+do|show\s+the\s+user\s+what\s+they\s+do|software\s+company(?:\s+website)?|company\s+website|agency\s+website|startup\s+showcase|agency|consultancy)\b/i.test(promptLower);

    // 3. Explicit backend command for the website application itself
    const explicitBackendTriggers = /\b(?:user\s+login\s+system|user\s+authentication\s+system|user\s+registration\s+system|shopping\s+cart\s+with\s+(?:stripe|checkout|payment)|(?:hotel\s+)?booking\s+(?:system|engine)\s+with\s+(?:live\s+)?database|(?:room|table)\s+reservation\s+(?:system\s+with\s+database|database)|admin\s+crud\s+portal|saas\s+dashboard\s+with\s+database\s+crud|full[\s\-]*stack\s+(?:web\s+)?app(?:lication)?\s+with\s+database|build\s+a\s+full[\s\-]*stack\s+app)\b/i;
    const hasExplicitBackend = explicitBackendTriggers.test(promptLower);

    if ((isHtmlCat || isShowcaseOrPortfolio) && !hasExplicitBackend) {
      return "html-css-js";
    }

    // 4. Scrub developer skills, experience, and bio from prompt
    // "React", "Python", "SQL", "Postgres", "FastAPI" when describing developer skills MUST NOT trigger fullstack
    let scrubbedPrompt = promptLower;
    const skillScrubPatterns = [
      /(?:skills?|technologies|tech\s+stack|tools?|languages?|proficiency)\s*[:\-][^\.\n;]+/g,
      /(?:skilled|experienced|proficient|worked|knowledge|background)\s+(?:in|with)\s+[^\.\n;]+/g,
      /(?:familiar|specializ(?:ed|ing))\s+(?:with|in)\s+[^\.\n;]+/g,
      /(?:projects?|apps?)\s+(?:built|developed|created)\s+(?:with|using|in)\s+[^\.\n;]+/g,
      /(?:full[\s\-]*stack|front[\s\-]*end|back[\s\-]*end|software|web|ui[\s\/]*ux|python|react|node|fastapi)\s+(?:developer|engineer|programmer|specialist|designer|creator|freelancer)/g,
      /\b(?:years?\s+of\s+experience|work\s+experience|career\s+highlights|job\s+history)\b[^\.\n;]*/g,
      /\b(?:react(?:\.?js)?|next(?:\.?js)?|vue(?:\.?js)?|angular|tailwind|typescript|javascript|html5?|css3?|python|fastapi|django|flask|postgresql?|sqlite3?|mongodb|mysql)\b/g,
    ];
    for (const pat of skillScrubPatterns) {
      scrubbedPrompt = scrubbedPrompt.replace(pat, " ");
    }

    const fullText = `${scrubbedPrompt} ${genreLower} ${categoryName}`;
    const dynamicBackendRegex = /\b(?:live\s+database|postgres(?:ql)?\s+database|sqlite\s+database|database\s+schema|database\s+crud|table\s+schema|persist\s+data\s+to\s+db|user\s+authentication|user\s+login|sign[\s\-]?in\s+portal|sign[\s\-]?up\s+portal|register\s+account|password\s+reset|jwt\s+tokens?|admin\s+panel|admin\s+dashboard|management\s+portal|crm\s+system|booking\s+system|reservation\s+system|shopping\s+cart|payment\s+gateway|stripe\s+checkout|process\s+payments?|order\s+management\s+system|fastapi\s+backend|rest\s+api\s+endpoints?|backend\s+service\s+with\s+database)\b/i;

    return dynamicBackendRegex.test(fullText) ? "react-fastapi-postgresql" : "html-css-js";
  }, [prompt, genre, categoryId, categories]);
  const stack = autoDetectedStack;

  const pipelineAgents = useMemo(() => {
    if (stack === "html-css-js") {
      return AGENTS.filter((a) => !["Architect Agent", "DB Schema Agent", "Backend Dev Agent"].includes(a));
    }
    return AGENTS;
  }, [stack]);

  // Restore state from store if available
  useEffect(() => {
    if (buildStore.plan && !plan) {
      setPlan(buildStore.plan);
      if (buildStore.prompt && !prompt) setPrompt(buildStore.prompt);
      if (buildStore.currentStep) setCurrentStep(buildStore.currentStep);
      if (buildStore.answers) setAnswers(buildStore.answers);
      if (buildStore.buildPrompt) setBuildPrompt(buildStore.buildPrompt);
      if (buildStore.uploadedAssets?.length) setUploadedAssets(buildStore.uploadedAssets);
    }
  }, [buildStore.plan]);

  const changeStep = (newStep) => {
    setCurrentStep(newStep);
    buildStore.setCurrentStep(newStep);
  };

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
    buildStore.setPlanning(true);
    buildStore.setPrompt(prompt);
    buildStore.setProjectTitle(genre || prompt.slice(0, 30));
    try {
      const token = await getToken();
      const result = await api.post("/studio/plan", {
        prompt,
        category: selectedCategory?.name || "Website",
        genre: genre.trim() || selectedCategory?.name || "Website",
        page_structure: effectivePageStructure,
        stack: stack || "html-css-js",
      }, token);
      const structuredPlan = {
        ...result.plan,
        pages: (result.plan.pages || []).map((page) => ({
          ...page,
          included: true,
          selected_sections: [...(page.sections || [])],
        })),
      };
      setPlan(structuredPlan);
      buildStore.setPlan(structuredPlan);
      const prefilled = result.plan.prefilled_answers || {};
      setAnswers(prefilled);
      buildStore.setAnswers(prefilled);
      const prefilledIds = Object.keys(prefilled).filter((k) => String(prefilled[k]).trim().length > 0);
      setCompletedQuestions(prefilledIds);
      setSkippedQuestions([]);
      setBuildPrompt("");
      changeStep(2);
    } catch (err) {
      setError(err.message || "The Planning Agent could not create a plan.");
    } finally {
      setLoadingPlan(false);
      buildStore.setPlanning(false);
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
        stack: stack || "html-css-js",
      }, token);
      setBuildPrompt(result.build_prompt || "");
    } catch (err) {
      setError(err.message || "The Planning Agent could not create the editable build prompt.");
    } finally {
      setLoadingBuildPrompt(false);
    }
  }

  async function startGeneration() {
    setError("");
    try {
      const token = await getToken();
      const effectiveCatId = categoryId || categories.find((c) => c.name?.toLowerCase() === (selectedCategory?.name || "").toLowerCase())?.id || categories[0]?.id || null;
      const effectiveCatName = selectedCategory?.name || categories.find((c) => c.id === effectiveCatId)?.name || "Website";
      await buildStore.startBuild({
        prompt,
        categoryId: effectiveCatId,
        categoryName: effectiveCatName,
        genre: genre.trim() || effectiveCatName || "Website",
        buildPrompt,
        plan,
        answers,
        uploadedAssets,
        stack: stack || "html-css-js",
        token,
        navigate,
      });
    } catch (err) {
      setError(err.message || "Studio generation failed. Your plan and answers are still here.");
    }
  }

  function deduceImageTarget(field, fileName) {
    const fieldRole = typeof field === "object" ? field?.role : field;
    const fieldLabel = typeof field === "object" ? field?.label : "";
    const fieldHint = typeof field === "object" ? field?.hint : "";
    const combined = `${fieldRole || ""} ${fieldLabel || ""} ${fieldHint || ""} ${fileName || ""}`.toLowerCase();

    const pages = (plan?.pages || []).filter((p) => p.included !== false || p.required);

    for (const p of pages) {
      const stem = p.filename.replace(/\.html$/, "").toLowerCase();
      const pName = (p.name || "").toLowerCase();
      if (combined.includes(stem) || (pName && combined.includes(pName))) {
        return { page_target: p.filename, role: stem };
      }
    }

    if (/\b(?:room|suite|bed|accommodation|stay|chamber)\b/i.test(combined)) {
      const match = pages.find((p) => /room|suite|stay/i.test(p.filename + (p.name || "")));
      return { page_target: match ? match.filename : "rooms.html", role: "rooms" };
    }
    if (/\b(?:dining|food|dish|restaurant|menu|chef|cuisine|eatery|bar|wine)\b/i.test(combined)) {
      const match = pages.find((p) => /dining|restaurant|menu|food/i.test(p.filename + (p.name || "")));
      return { page_target: match ? match.filename : "dining.html", role: "dining" };
    }
    if (/\b(?:amenit|spa|pool|gym|fitness|wellness|conference|boardroom|meeting)\b/i.test(combined)) {
      const match = pages.find((p) => /amenit|spa|wellness|facility/i.test(p.filename + (p.name || "")));
      return { page_target: match ? match.filename : "amenities.html", role: "amenities" };
    }
    if (/\b(?:contact|reach|location|map|address|concierge|reception|lobby)\b/i.test(combined)) {
      const match = pages.find((p) => /contact|location/i.test(p.filename + (p.name || "")));
      return { page_target: match ? match.filename : "contact.html", role: "contact" };
    }
    if (/\b(?:façade|facade|exterior|entrance|building|hero|banner|cover)\b/i.test(combined)) {
      return { page_target: "index.html", role: "hero" };
    }
    if (/\b(?:logo|brand|signage)\b/i.test(combined)) {
      return { page_target: "all", role: "logo" };
    }
    if (/\b(?:portrait|profile|avatar|team|staff|founder|headshot)\b/i.test(combined)) {
      const match = pages.find((p) => /about|team/i.test(p.filename + (p.name || "")));
      return { page_target: match ? match.filename : "index.html", role: "portrait" };
    }

    return { page_target: "index.html", role: fieldRole || "general" };
  }

  async function uploadPortfolioImages(fieldOrRole, fileList) {
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

        const cleanName = file.name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ");
        const { page_target, role } = deduceImageTarget(fieldOrRole, file.name);

        let defaultTitle = cleanName;
        if (/^images?\s*\(\d+\)$/i.test(cleanName) || /^unnamed$/i.test(cleanName)) {
          const fieldLabel = typeof fieldOrRole === "object" ? fieldOrRole.label : "";
          defaultTitle = fieldLabel ? `${fieldLabel} photo` : cleanName;
        }

        setUploadedAssets((current) => [
          ...current,
          {
            url: result.url,
            name: file.name,
            role,
            page_target,
            title: defaultTitle,
            alt: defaultTitle,
            caption: "",
            section_target: "content",
          },
        ]);
        setBuildPrompt("");
      }
    } catch (err) {
      setError(err.message || "Image upload failed.");
    } finally {
      setUploadingImages(false);
    }
  }

  function updateUploadedAsset(index, updates) {
    setUploadedAssets((current) =>
      current.map((item, i) => (i === index ? { ...item, ...updates } : item))
    );
    setBuildPrompt("");
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
            <p>Shape the plan, and let nine focused agents analyze your requirements and build your website or full-stack application.</p>
          </div>
          <div className="studio-agent-preview" aria-label="Studio workflow">
            <span className="studio-agent-orbit"><Sparkles size={22} /></span>
            <span className="studio-agent-caption">YOUR BUILD TEAM</span>
            <strong>Nine agents.<br />One finished site.</strong>
            <div className="studio-agent-dots">{AGENTS.map((agent, index) => <i key={agent} title={agent} className={index === 0 ? "active" : ""} />)}</div>
            <small>Plan · Architect · Database · Backend · Frontend · Review</small>
          </div>
        </div>

        {loadingPlan ? (
          /* ── Planning Agent Loading Screen ── */
          <div className="flex flex-col items-center justify-center rounded-3xl border border-violet-500/20 bg-gradient-to-b from-violet-950/30 via-[#0c111b] to-[#070b12] p-8 sm:p-14 text-center shadow-2xl relative overflow-hidden my-6">
            <div className="absolute top-0 right-0 -mr-20 -mt-20 h-64 w-64 rounded-full bg-violet-600/15 blur-3xl pointer-events-none" />
            <div className="relative mb-6">
              <div className="flex h-20 w-20 items-center justify-center rounded-2xl border border-violet-400/30 bg-violet-500/10 shadow-lg shadow-violet-500/20">
                <Brain className="h-9 w-9 text-violet-300 animate-pulse" />
              </div>
              <div className="absolute -inset-2 rounded-3xl bg-violet-500/10 blur-xl animate-pulse -z-10" />
            </div>

            <div className="inline-flex items-center gap-2 rounded-full border border-violet-500/30 bg-violet-500/10 px-3.5 py-1 text-xs font-bold text-violet-300 mb-3">
              <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
              <span>Planning Agent Active</span>
            </div>

            <h2 className="text-2xl sm:text-3xl font-extrabold text-white">
              Architecting Your Project Plan...
            </h2>
            <p className="mt-2 text-sm text-slate-400 max-w-lg leading-relaxed">
              Analyzing requirements for <span className="text-violet-300 font-semibold">{genre || selectedCategory?.name || "your website"}</span> to design the page structure, section components, and creative direction.
            </p>

            <div className="mt-8 grid gap-2.5 w-full max-w-md text-left">
              <div className="flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.02] p-3 text-xs text-slate-300">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400 text-[10px] font-bold">✓</span>
                <span>Semantic requirement &amp; domain analysis</span>
              </div>
              <div className="flex items-center gap-3 rounded-xl border border-violet-500/20 bg-violet-500/10 p-3 text-xs text-violet-200">
                <LoaderCircle className="h-4 w-4 shrink-0 animate-spin text-violet-400" />
                <span className="font-medium">Evaluating full-stack vs static architecture</span>
              </div>
              <div className="flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.02] p-3 text-xs text-slate-400">
                <span className="h-2 w-2 rounded-full bg-slate-600 ml-1.5 mr-1" />
                <span>Synthesizing page blueprints &amp; section components</span>
              </div>
              <div className="flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.02] p-3 text-xs text-slate-400">
                <span className="h-2 w-2 rounded-full bg-slate-600 ml-1.5 mr-1" />
                <span>Curating design system, typography &amp; color palette</span>
              </div>
            </div>
          </div>
        ) : !plan ? (
          /* ── Step 1: Initial Prompt & Details Form ── */
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
              <WandSparkles size={17} />
              <span>Plan my website</span>
              <ArrowRight size={16} />
            </button>
          </form>
        ) : isGenerating ? (
          /* ── Step 5: Multi-Agent Live Generation Screen ── */
          <div className="rounded-3xl border border-violet-500/20 bg-gradient-to-b from-violet-950/20 via-[#0c111b] to-[#070b12] p-6 sm:p-10 shadow-2xl">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-6">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-500/20 border border-violet-400/30 text-violet-300">
                  <LoaderCircle size={24} className="animate-spin text-violet-300" />
                </div>
                <div>
                  <p className="text-xs font-bold uppercase tracking-widest text-violet-300">Building In Progress</p>
                  <h2 className="text-xl font-extrabold text-white">{currentActiveAgent || "Nine Focused Agents Working"}</h2>
                </div>
              </div>
              <span className="rounded-full bg-violet-500/10 border border-violet-500/30 px-3 py-1 text-xs font-bold text-violet-300">
                Multi-Agent Pipeline
              </span>
            </div>

            <div className="grid gap-6 lg:grid-cols-2 mt-8">
              {/* Agent Status List */}
              <div className="rounded-2xl border border-white/10 bg-[#090d16] p-5">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4">Pipeline Execution</h3>
                <div className="space-y-3">
                  {pipelineAgents.map((name) => {
                    const currentIndex = pipelineAgents.indexOf(currentActiveAgent);
                    const myIndex = pipelineAgents.indexOf(name);
                    const failed = currentEvents.some((event) => event.agent === name && event.status === "failed");
                    const isDoneExplicit = currentEvents.some((event) => event.agent === name && event.status === "completed");
                    const done = !failed && (isDoneExplicit || (currentIndex > myIndex && currentIndex !== -1));
                    const active = currentActiveAgent === name;
                    return (
                      <div key={name} className={`flex items-center justify-between rounded-xl p-2.5 text-xs transition ${done ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-300" : failed ? "bg-amber-500/10 border border-amber-500/20 text-amber-300" : active ? "bg-violet-500/20 border border-violet-500/40 text-white font-bold" : "text-slate-500 border border-transparent"}`}>
                        <div className="flex items-center gap-2.5">
                          {done ? (
                            <CheckCircle2 size={15} className="text-emerald-400" />
                          ) : failed ? (
                            <AlertCircle size={15} className="text-amber-300" />
                          ) : active ? (
                            <LoaderCircle size={15} className="animate-spin text-violet-300" />
                          ) : (
                            <span className="h-3.5 w-3.5 rounded-full border border-slate-700" />
                          )}
                          <span>{name}</span>
                        </div>
                        <span className="text-[10px] font-semibold uppercase opacity-75">
                          {done ? "Completed" : active ? "Active" : failed ? "Warning" : "Queued"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Live Streaming Logs */}
              <div className="flex flex-col rounded-2xl border border-white/10 bg-[#090d16] p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Live Agent Stream</h3>
                  <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                </div>
                <div className="flex-1 max-h-80 space-y-2 overflow-y-auto pr-1 font-mono text-[11px] text-slate-400">
                  {currentEvents.length === 0 ? (
                    <p className="text-slate-600 italic">Initializing multi-agent session...</p>
                  ) : (
                    currentEvents.map((event) => {
                      const agentLabel = event.agent || (event.type === "page" ? "Frontend Dev Agent" : "Pipeline");
                      const detailText = event.detail || (event.type === "page" && event.name ? `Building ${event.name} page (${event.filename || "HTML"})…` : event.name || event.message || event.type);
                      return (
                        <div key={event.key} className="rounded-lg bg-black/30 p-2 border border-white/5">
                          <span className="text-violet-300 font-semibold">{agentLabel}:</span>{" "}
                          <span className="text-slate-300">{detailText}</span>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* ── Post-Plan Multi-Page Step Workflow ── */
          <div className="space-y-6">
            {/* Top Stepper Navigation */}
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-5">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    if (currentStep === 2) {
                      setPlan(null);
                      changeStep(1);
                    } else {
                      setCurrentStep((prev) => Math.max(1, prev - 1));
                    }
                  }}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3.5 py-2 text-xs font-semibold text-slate-300 hover:bg-white/10 hover:text-white transition"
                >
                  <ArrowLeft size={14} /> Back
                </button>
                <div>
                  <span className="text-xs uppercase tracking-wider text-violet-400 font-bold">Project Plan</span>
                  <h2 className="text-lg font-bold text-white truncate max-w-sm sm:max-w-md">{plan.title}</h2>
                </div>
              </div>

              <div className="flex items-center gap-1.5 rounded-2xl border border-white/10 bg-black/40 p-1.5">
                {[
                  { step: 2, label: "1. Pages & Design" },
                  { step: 3, label: `2. Questions (${completedQuestions.length}/${clarificationQuestions.length})` },
                  { step: 4, label: "3. Assets & Build" },
                ].map((s) => (
                  <button
                    key={s.step}
                    type="button"
                    onClick={() => setCurrentStep(s.step)}
                    className={`rounded-xl px-3.5 py-1.5 text-xs font-bold transition ${
                      currentStep === s.step
                        ? "bg-violet-600 text-white shadow-md shadow-violet-600/30"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* ── STEP 2: Pages & Architecture Blueprint ── */}
            {currentStep === 2 && (
              <div className="space-y-6">
                <div className="rounded-3xl border border-white/10 bg-white/[0.035] p-5 sm:p-7">
                  <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-300">Planning Agent · Proposal</p>
                      <h2 className="mt-2 text-2xl font-bold">{plan.title}</h2>
                      <p className="mt-2 text-sm leading-6 text-slate-400 max-w-3xl">{plan.summary}</p>
                    </div>
                    <span className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300">
                      {selectedPageCount} of {plan.pages.length} pages · {selectedPageCount === 1 ? "single page" : "multi page"}
                    </span>
                  </div>

                  <div className="mb-4 flex items-center justify-between gap-3 border-b border-white/10 pb-3">
                    <div>
                      <h3 className="text-sm font-bold">Included Pages &amp; Sections</h3>
                      <p className="mt-1 text-xs text-slate-500">Home is required. Toggle other pages or select individual sections per page.</p>
                    </div>
                    <span className="shrink-0 rounded-full bg-violet-400/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-violet-200">
                      {selectedPageCount} selected
                    </span>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    {plan.pages.map((page, index) => (
                      <article key={page.filename} className={`rounded-2xl border bg-[#0c111b] p-4 transition ${page.included === false ? "border-white/5 opacity-60" : "border-white/10 hover:border-violet-500/30"}`}>
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <label className="flex cursor-pointer items-center gap-3">
                            <input type="checkbox" checked={page.included !== false || page.required} disabled={!!page.required} onChange={() => togglePlanPage(page.filename)} className="h-4 w-4 accent-violet-400 disabled:cursor-not-allowed" />
                            <span className="font-semibold text-sm">{String(index + 1).padStart(2, "0")} · {page.name}</span>
                          </label>
                          <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${page.required ? "bg-amber-300/10 text-amber-200" : "bg-white/5 text-slate-500"}`}>
                            {page.required ? "Required" : page.included === false ? "Excluded" : "Optional"}
                          </span>
                        </div>
                        <p className="mt-2 text-xs text-slate-400">{page.purpose}</p>
                        {!!page.sections?.length && (
                          <div className="mt-3">
                            <p className="mb-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Sections</p>
                            <div className="flex flex-wrap gap-1.5">
                              {page.sections.map((section) => {
                                const selected = (page.selected_sections || page.sections).includes(section);
                                return (
                                  <button key={section} type="button" disabled={page.included === false} aria-pressed={selected} onClick={() => togglePageSection(page.filename, section)} className={`rounded-lg border px-2 py-1 text-[11px] transition ${selected ? "border-violet-400/40 bg-violet-400/10 text-violet-100" : "border-white/10 bg-transparent text-slate-500 hover:text-slate-300"} disabled:cursor-not-allowed disabled:opacity-40`}>
                                    {selected ? "✓ " : "+ "}{section}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </article>
                    ))}
                  </div>

                  {plan.design_direction && (
                    <div className="mt-5 rounded-2xl border border-violet-400/15 bg-violet-400/[0.06] p-4">
                      <h3 className="text-sm font-semibold text-violet-200">Creative Direction</h3>
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">{plan.design_direction}</p>
                    </div>
                  )}
                </div>

                {/* Visual Concept */}
                <div className="rounded-3xl border border-white/10 bg-white/[0.035] p-5 sm:p-7">
                  <div className="mb-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-300">UI Designer Agent · Visual Concept</p>
                    <h2 className="mt-2 text-xl font-bold">Planned Visual Direction &amp; Color Scheme</h2>
                  </div>
                  <div className="overflow-hidden rounded-2xl border border-black/10 shadow-xl" style={{ backgroundColor: safeColor(palette.background, "#f3f4f6"), color: safeColor(palette.text, "#172033") }}>
                    <div className="flex items-center justify-between border-b border-black/10 px-4 py-3 text-xs">
                      <strong>{plan.title}</strong>
                      <div className="hidden gap-4 sm:flex">{plan.pages.filter((page) => page.included !== false || page.required).slice(0, 3).map((page) => <span key={page.filename} className="opacity-70">{page.name}</span>)}</div>
                    </div>
                    <div className="grid min-h-[220px] items-center gap-5 p-5 sm:grid-cols-[1.05fr_0.95fr] sm:p-8">
                      <div>
                        <span className="text-[10px] font-bold uppercase tracking-[0.2em]" style={{ color: safeColor(palette.primary, "#6d4aff") }}>{genre || selectedCategory?.name || "Website"}</span>
                        <h3 className="mt-3 text-2xl sm:text-3xl font-black leading-tight">{plan.preview?.headline || plan.title}</h3>
                        <p className="mt-2 max-w-md text-xs sm:text-sm leading-relaxed opacity-70">{plan.preview?.subheadline || plan.summary}</p>
                        <span className="mt-4 inline-flex rounded-lg px-4 py-2 text-xs font-bold text-white" style={{ backgroundColor: safeColor(palette.primary, "#6d4aff") }}>{plan.preview?.primary_action || "Explore"}</span>
                      </div>
                      <div className="relative min-h-[140px] overflow-hidden rounded-2xl" style={{ background: `linear-gradient(135deg, ${safeColor(palette.primary, "#6d4aff")}55, ${safeColor(palette.accent, "#f28a64")}66)` }}>
                        {previewImage && <img src={previewImage} alt="Selected visual direction" className="absolute inset-0 h-full w-full object-cover" />}
                        <div className="absolute inset-0" style={{ background: `linear-gradient(135deg, ${safeColor(palette.primary, "#6d4aff")}55, transparent 75%)` }} />
                        <div className="absolute bottom-3 left-3 rounded-lg px-3 py-1.5 text-[10px] font-semibold text-white backdrop-blur" style={{ backgroundColor: `${safeColor(palette.surface, "#ffffff")}44` }}>{palette.image_treatment || "Visual story"}</div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Bottom Step Actions */}
                <div className="flex items-center justify-between pt-4 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => { setPlan(null); changeStep(1); }}
                    className="rounded-xl border border-white/10 bg-white/5 px-5 py-3 text-xs font-bold text-slate-300 hover:bg-white/10 hover:text-white transition"
                  >
                    ← Edit Project Brief
                  </button>
                  <button
                    type="button"
                    onClick={() => changeStep(3)}
                    className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-6 py-3 text-xs font-bold text-white shadow-lg shadow-violet-600/25 hover:bg-violet-500 transition"
                  >
                    <span>Continue to Clarifications (Step 2)</span>
                    <ArrowRight size={15} />
                  </button>
                </div>
              </div>
            )}

            {/* ── STEP 3: Clarification Questions ── */}
            {currentStep === 3 && (
              <div className="space-y-6">
                <div className="rounded-3xl border border-white/10 bg-white/[0.035] p-5 sm:p-8">
                  <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-300">Step 2 · Clarifications</p>
                      <h2 className="mt-1 text-2xl font-bold">Answer key project questions</h2>
                      <p className="mt-1 text-sm text-slate-400">Answer these targeted questions to help the agents tailor your copy and sections.</p>
                    </div>
                    <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-3.5 py-1 text-xs font-bold text-violet-300">
                      {completedQuestions.length + skippedQuestions.length} of {clarificationQuestions.length} answered
                    </span>
                  </div>

                  <div className="space-y-4 max-w-2xl mx-auto">
                    {(plan.questions || []).map((question, index) => {
                      const id = question.id || `q-${index}`;
                      const wasAnswered = completedQuestions.includes(id);
                      const wasSkipped = skippedQuestions.includes(id);
                      if (!wasAnswered && !wasSkipped) return null;
                      return (
                        <div key={id} className="space-y-2">
                          <div className="max-w-[90%] rounded-2xl rounded-bl-sm border border-white/10 bg-[#0c111b] px-4 py-3 text-sm text-slate-300">{question.question}</div>
                          <div className="ml-auto max-w-[90%] rounded-2xl rounded-br-sm bg-violet-500/15 px-4 py-3 text-sm text-violet-100">{wasSkipped ? "Skip for now" : answers[id]}</div>
                        </div>
                      );
                    })}

                    {activeClarificationIndex >= 0 ? (() => {
                      const question = clarificationQuestions[activeClarificationIndex];
                      const id = question.id || `q-${activeClarificationIndex}`;
                      const value = answers[id] || "";
                      return (
                        <div className="rounded-2xl border border-violet-400/20 bg-violet-400/[0.07] p-5 space-y-4" key={id}>
                          <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-wider text-violet-300">
                            <span>Studio Question #{completedQuestions.length + skippedQuestions.length + 1}</span>
                            <span>{completedQuestions.length + skippedQuestions.length + 1} / {clarificationQuestions.length}</span>
                          </div>
                          <label htmlFor={`active-${id}`} className="block text-sm font-semibold text-white leading-relaxed">
                            {question.question}{question.required && <span className="ml-1 text-violet-300">*</span>}
                          </label>
                          {question.input_type === "select" ? (
                            <select id={`active-${id}`} value={value} onChange={(event) => updateAnswer(id, event.target.value)} className="w-full rounded-xl border border-white/10 bg-[#0c111b] px-4 py-3 text-sm text-white outline-none focus:border-violet-400">
                              <option value="">Choose an answer</option>
                              {(question.options || []).map((option) => <option key={option} value={option}>{option}</option>)}
                            </select>
                          ) : question.input_type === "textarea" ? (
                            <textarea id={`active-${id}`} value={value} onChange={(event) => updateAnswer(id, event.target.value)} placeholder={question.placeholder || "Type your answer…"} rows={4} className="w-full rounded-xl border border-white/10 bg-[#0c111b] px-4 py-3 text-sm text-white placeholder:text-slate-600 outline-none focus:border-violet-400" />
                          ) : (
                            <input id={`active-${id}`} value={value} onChange={(event) => updateAnswer(id, event.target.value)} placeholder={question.placeholder || "Type your answer…"} className="w-full rounded-xl border border-white/10 bg-[#0c111b] px-4 py-3 text-sm text-white placeholder:text-slate-600 outline-none focus:border-violet-400" />
                          )}
                          <div className="flex justify-end gap-2.5 pt-2">
                            {!question.required && (
                              <button type="button" onClick={() => submitClarification(question, activeClarificationIndex)} className="rounded-xl border border-white/10 px-4 py-2.5 text-xs font-semibold text-slate-300 hover:bg-white/5 transition">
                                Skip
                              </button>
                            )}
                            <button type="button" onClick={() => submitClarification(question, activeClarificationIndex)} disabled={!value.trim()} className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-violet-600/30 hover:bg-violet-500 disabled:opacity-40 transition">
                              <span>Next Answer</span>
                              <ArrowRight size={14} />
                            </button>
                          </div>
                        </div>
                      );
                    })() : (
                      <div className="rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.08] p-5 text-center">
                        <CheckCircle2 className="h-8 w-8 text-emerald-400 mx-auto mb-2" />
                        <h4 className="font-bold text-emerald-300">All questions answered!</h4>
                        <p className="mt-1 text-xs text-slate-300">You are ready to upload images and review your project prompt.</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Bottom Step Actions */}
                <div className="flex items-center justify-between pt-4 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => changeStep(2)}
                    className="rounded-xl border border-white/10 bg-white/5 px-5 py-3 text-xs font-bold text-slate-300 hover:bg-white/10 hover:text-white transition"
                  >
                    ← Back to Pages &amp; Blueprint
                  </button>
                  <button
                    type="button"
                    onClick={() => changeStep(4)}
                    className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-6 py-3 text-xs font-bold text-white shadow-lg shadow-violet-600/25 hover:bg-violet-500 transition"
                  >
                    <span>Continue to Assets &amp; Build (Step 3)</span>
                    <ArrowRight size={15} />
                  </button>
                </div>
              </div>
            )}

            {/* ── STEP 4: Assets & Build Prompt ── */}
            {currentStep === 4 && (
              <div className="space-y-6">
                <div className="grid gap-6 lg:grid-cols-2">
                  {/* Left: Image Assets */}
                  <div className="rounded-3xl border border-white/10 bg-white/[0.035] p-5 sm:p-7">
                    <div className="flex items-center gap-2 mb-2">
                      <ImagePlus size={18} className="text-violet-300" />
                      <h3 className="font-bold text-base text-white">Choose Images &amp; Logos</h3>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Upload up to 16 images for your site. If left empty, Studio automatically uses relevant high-quality stock photos.
                    </p>

                    <div className="mt-4 space-y-2.5">
                      {uploadFields.map((field) => (
                        <label key={`${field.role}-${field.label}`} className="block rounded-xl border border-white/10 bg-[#0c111b] p-3 transition hover:border-violet-500/30">
                          <span className="block text-xs font-semibold text-slate-200">{field.label}</span>
                          <span className="mt-0.5 block text-[11px] text-slate-500">{field.hint}</span>
                          <input className="mt-2 block w-full text-xs text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-violet-500/15 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-violet-200" type="file" accept="image/*" multiple={field.multiple} disabled={uploadingImages || uploadedAssets.length >= 16} onChange={(event) => { uploadPortfolioImages(field, event.target.files); event.target.value = ""; }} />
                        </label>
                      ))}
                    </div>

                    {uploadedAssets.length > 0 && (
                      <div className="mt-5 space-y-3">
                        <div className="flex items-center justify-between border-t border-white/10 pt-4">
                          <span className="text-xs font-bold uppercase tracking-wider text-violet-300">
                            Uploaded Photos ({uploadedAssets.length}/16)
                          </span>
                        </div>
                        <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                          {uploadedAssets.map((asset, index) => (
                            <div key={`${asset.url}-${index}`} className="flex items-center gap-3 rounded-xl border border-white/10 bg-[#0a0e17] p-2 text-xs">
                              <img src={asset.url} alt="" className="h-10 w-10 rounded-lg object-cover" />
                              <div className="flex-1 truncate">
                                <p className="font-semibold text-white truncate">{asset.title || "Custom Photo"}</p>
                                <p className="text-[10px] text-violet-300">{asset.role} · {asset.page_target || "index.html"}</p>
                              </div>
                              <button type="button" onClick={() => setUploadedAssets((curr) => curr.filter((_, i) => i !== index))} className="text-slate-500 hover:text-rose-400 p-1">
                                <Trash2 size={13} />
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Right: Editable Build Prompt */}
                  <div className="rounded-3xl border border-white/10 bg-white/[0.035] p-5 sm:p-7 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <h3 className="font-bold text-base text-white">Full Build Brief</h3>
                        <span className="rounded-full bg-violet-500/10 border border-violet-500/30 px-2.5 py-0.5 text-[10px] font-bold text-violet-300">Ready to Code</span>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed mb-4">
                        The Planning Agent compiles your answers and architecture into a full blueprint for the code agents.
                      </p>

                      {!buildPrompt ? (
                        <div className="rounded-2xl border border-dashed border-white/10 bg-black/30 p-8 text-center">
                          <FileText className="h-8 w-8 text-violet-400 mx-auto mb-2 opacity-60" />
                          <p className="text-xs text-slate-400">Click below to generate and preview the editable code brief.</p>
                          <button
                            type="button"
                            onClick={createBuildPrompt}
                            disabled={loadingBuildPrompt}
                            className="mt-4 inline-flex items-center gap-2 rounded-xl bg-violet-600 px-5 py-2.5 text-xs font-bold text-white hover:bg-violet-500 transition"
                          >
                            {loadingBuildPrompt ? <LoaderCircle size={15} className="animate-spin" /> : <WandSparkles size={15} />}
                            <span>{loadingBuildPrompt ? "Generating Brief..." : "Create Project Brief"}</span>
                          </button>
                        </div>
                      ) : (
                        <div className="space-y-3">
                          <textarea
                            value={buildPrompt}
                            maxLength={60000}
                            onChange={(e) => setBuildPrompt(e.target.value)}
                            rows={10}
                            className="w-full resize-y rounded-xl border border-white/10 bg-[#080b12] p-3 font-mono text-xs leading-5 text-slate-200 outline-none focus:border-violet-400"
                          />
                          <button
                            type="button"
                            onClick={createBuildPrompt}
                            disabled={loadingBuildPrompt}
                            className="w-full rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-300 hover:bg-white/5 transition"
                          >
                            {loadingBuildPrompt ? "Updating..." : "Refresh from Q&amp;A"}
                          </button>
                        </div>
                      )}
                    </div>

                    <div className="pt-6 border-t border-white/10 mt-6 space-y-3">
                      <button
                        type="button"
                        onClick={startGeneration}
                        disabled={!buildPrompt || buildPrompt.trim().length < 50}
                        className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 via-indigo-600 to-violet-700 py-3.5 px-4 text-sm font-extrabold text-white shadow-xl shadow-violet-600/30 hover:opacity-95 transition disabled:opacity-40 cursor-pointer"
                      >
                        <WandSparkles size={17} />
                        <span>Build My Website</span>
                        <ArrowRight size={16} />
                      </button>
                      <p className="text-center text-[11px] text-slate-500">
                        Agents build, test, and package your site. Once complete, you will be taken to your Launch Hub.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Bottom Step Actions */}
                <div className="flex items-center justify-between pt-4 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => changeStep(3)}
                    className="rounded-xl border border-white/10 bg-white/5 px-5 py-3 text-xs font-bold text-slate-300 hover:bg-white/10 hover:text-white transition"
                  >
                    ← Back to Questions
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
