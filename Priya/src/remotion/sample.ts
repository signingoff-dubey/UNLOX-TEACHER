import type { Scene, Track } from "../types";

// Silent preview lesson for `npm run studio`: shows every template without the backend.
type Draft = Partial<Scene> & Pick<Scene, "template" | "heading" | "narration">;

const drafts: Draft[] = [
  { template: "title", heading: "Why does it rain?", icon: "cloud",
    narration: "Have you ever wondered where rain comes from?" },
  { template: "cycle", heading: "The water cycle", icon: "water",
    items: ["Evaporation", "Condensation", "Precipitation", "Collection"],
    narration: "The sun heats water and it evaporates. Vapour condenses into clouds. Rain falls, and water collects again." },
  { template: "diagram", heading: "Cloud", icon: "cloud",
    items: ["Water droplets", "Dust", "Cool air"],
    narration: "A cloud is made of tiny water droplets that form around dust in cool air." },
  { template: "flow", heading: "From sea to rain", icon: "sun",
    items: ["Sun heats sea", "Vapour rises", "Clouds form", "Rain falls"],
    narration: "The sun heats the sea, vapour rises, clouds form, and finally rain falls." },
  { template: "compare", heading: "Weather vs climate", icon: "earth",
    left_title: "Weather", left: ["Today", "Changes fast"],
    right_title: "Climate", right: ["Many years", "Changes slowly"],
    narration: "Weather is what happens today and changes fast. Climate is the pattern over many years." },
  { template: "bullets", heading: "Monsoon facts", icon: "cloud",
    items: ["June to September", "Winds from the sea", "Feeds our farms"],
    narration: "India's monsoon arrives in June, brings winds from the sea, and feeds our farms." },
  { template: "quiz", heading: "What forms clouds?", icon: "lightbulb",
    items: ["Smoke", "Condensation", "Wind"], answer_index: 1,
    narration: "What forms clouds? The answer is condensation of water vapour." },
  { template: "summary", heading: "Remember", icon: "lightbulb",
    items: ["Water evaporates", "Clouds condense", "Rain returns it"],
    narration: "Water evaporates, condenses into clouds, and rain returns it to the earth." },
];

let start = 0;
const scenes: Scene[] = drafts.map((d) => {
  const speech_s = Math.max(2.5, d.narration.length / 14);
  const scene: Scene = {
    items: [], icon: "lightbulb", left_title: "", right_title: "", left: [], right: [], answer_index: 0,
    ...d,
    speech_s,
    duration_s: speech_s + 0.5,
    start_s: start,
    captions: [{ start: 0, end: speech_s, text: d.narration }],
  };
  start += scene.duration_s;
  return scene;
});

export const sampleTrack: Track = {
  lang: "en", name: "English", native: "English", title: "Rain and the water cycle",
  scenes, duration_s: start, tts_engines: ["silent"],
};
