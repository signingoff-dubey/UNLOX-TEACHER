export type Quiz = {
  q: string;
  options: string[];
  answer: number;
  hint: string;
  /** Why the answer is right, shown after a correct answer. */
  why?: string;
};

export type Zone = {
  name: string;
  color: string;
  info: {
    title: string;
    body: string;
    terms: string[];
    code?: string;
    /** More to read at the station: study-guide points, FAQ answers, timeline steps, mind-map branches... */
    extra?: { label: string; text: string }[];
  };
  quiz: Quiz;
  /** More questions at the same gate. The gate opens when every question has been answered. */
  more?: Quiz[];
};

/** One walkable world: a few knowledge stations, each followed by a quiz gate. */
export type World = {
  title: string;
  /** Lower-case text the topic box is matched against. Defaults to the title. */
  match?: string;
  zones: Zone[];
  finale: { title: string; body: string };
};
