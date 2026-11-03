import { create } from "zustand";
import { API_URL } from "@/lib/api";

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

export const useStudioBuildStore = create((set, get) => ({
  isBuilding: false,
  isComplete: false,
  isPlanning: false,
  projectTitle: "",
  genre: "",
  categoryId: "",
  categoryName: "",
  prompt: "",
  plan: null,
  currentStep: 1,
  answers: {},
  buildPrompt: "",
  uploadedAssets: [],
  activeAgent: "Planning Agent",
  progress: 0,
  events: [],
  buildSessionId: "",
  completedTemplateId: "",
  error: null,
  isMinimized: false,
  lastNavigation: null,

  setPlanning: (val) => set({ isPlanning: val }),
  setPlan: (plan) => set({ plan }),
  setPrompt: (prompt) => set({ prompt }),
  setCurrentStep: (currentStep) => set({ currentStep }),
  setProjectTitle: (projectTitle) => set({ projectTitle }),
  setAnswers: (answers) => set({ answers }),
  setBuildPrompt: (buildPrompt) => set({ buildPrompt }),
  setUploadedAssets: (uploadedAssets) => set({ uploadedAssets }),
  toggleMinimized: () => set((s) => ({ isMinimized: !s.isMinimized })),
  setMinimized: (val) => set({ isMinimized: val }),

  resetBuild: () => set({
    isBuilding: false,
    isComplete: false,
    isPlanning: false,
    events: [],
    progress: 0,
    activeAgent: "",
    completedTemplateId: "",
    error: null,
  }),

  startBuild: async ({
    prompt,
    categoryId,
    categoryName,
    genre,
    buildPrompt,
    plan,
    answers,
    uploadedAssets,
    stack,
    token,
    navigate,
  }) => {
    const title = plan?.title || genre || "Custom Website";
    set({
      isBuilding: true,
      isComplete: false,
      error: null,
      events: [],
      progress: 10,
      projectTitle: title,
      activeAgent: AGENTS[0],
      buildSessionId: "",
      completedTemplateId: "",
    });

    try {
      const response = await fetch(`${API_URL}/studio/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          prompt,
          category_id: categoryId && String(categoryId).trim() !== "" ? categoryId : null,
          category: categoryName || "Website",
          genre: genre.trim() || categoryName || "Website",
          build_prompt: buildPrompt,
          plan,
          answers,
          image_urls: [],
          image_assets: uploadedAssets,
          stack: stack || "html-css-js",
        }),
      });

      if (!response.ok || !response.body) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Could not start website generation.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let buildCompleted = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        const frames = buffer.split("\n\n");
        buffer = frames.pop() || "";

        for (const frame of frames) {
          const line = frame.split("\n").find((part) => part.startsWith("data: "));
          if (!line) continue;
          let item = null;
          try {
            item = JSON.parse(line.slice(6));
          } catch (e) {
            continue;
          }

          if (item.type === "error") throw new Error(item.message || "Studio generation failed.");
          if (item.type === "session") {
            set({ buildSessionId: item.build_id || "" });
          }

          if (item.type === "agent") {
            const activePipelineList = stack === "html-css-js"
              ? AGENTS.filter((a) => !["Architect Agent", "DB Schema Agent", "Backend Dev Agent"].includes(a))
              : AGENTS;
            const agentIndex = activePipelineList.indexOf(item.agent);
            const calculatedProgress = agentIndex >= 0 ? Math.min(95, Math.round(((agentIndex + 1) / activePipelineList.length) * 100)) : get().progress;
            set((state) => ({
              activeAgent: item.agent,
              progress: Math.max(state.progress, calculatedProgress),
              events: [...state.events, { ...item, key: `${item.agent}-${item.status}-${state.events.length}` }],
            }));
          } else if (item.type === "page") {
            set((state) => ({
              activeAgent: "Frontend Dev Agent",
              progress: Math.min(95, state.progress + 4),
              events: [...state.events, { ...item, key: `${item.filename}-${item.status}-${state.events.length}` }],
            }));
          } else if (item.type === "model") {
            set((state) => ({
              events: [...state.events, { ...item, key: `${item.page}-${item.provider}-${state.events.length}` }],
            }));
          } else if (item.type === "complete") {
            buildCompleted = true;
            const newTemplateId = item.project?.id || "";
            const currentBuildId = get().buildSessionId;
            const buildQuery = currentBuildId ? `&build=${encodeURIComponent(currentBuildId)}` : "";
            
            set({
              isBuilding: false,
              isComplete: true,
              progress: 100,
              completedTemplateId: newTemplateId,
              activeAgent: "Completed",
            });

            // Automatically move to the new Launch Hub page
            if (navigate) {
              navigate(`/studio/launch?template=${encodeURIComponent(newTemplateId)}${buildQuery}`);
            }
            return;
          }
        }
      }

      if (!buildCompleted) {
        throw new Error("Generation stream closed before completion.");
      }
    } catch (err) {
      set({
        isBuilding: false,
        error: err.message || "Studio generation failed.",
      });
      throw err;
    }
  },
}));

