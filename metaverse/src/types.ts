export type Quiz = { q: string; options: string[]; answer: number; hint: string };

export type Zone = {
  name: string;
  color: string;
  info: { title: string; body: string; terms: string[]; code?: string };
  quiz: Quiz;
};

/** One walkable world: a few knowledge stations, each followed by a quiz gate. */
export type World = {
  title: string;
  /** Lower-case text the topic box is matched against. Defaults to the title. */
  match?: string;
  zones: Zone[];
  finale: { title: string; body: string };
};
