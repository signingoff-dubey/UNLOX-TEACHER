import React from "react";

// 5x7 dot-matrix glyphs for the display numbers ("#" = lit dot).
const GLYPHS: Record<string, string[]> = {
  "0": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
  "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
  "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
  "3": ["#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."],
  "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
  "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
  "6": ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
  "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
  "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
  "9": [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
  ".": [".", ".", ".", ".", ".", ".", "#"],
  ":": [".", ".", "#", ".", "#", ".", "."],
  "-": ["...", "...", "...", "###", "...", "...", "..."],
  "%": ["##..#", "##..#", "...#.", "..#..", ".#...", "#..##", "#..##"],
};

/** A number drawn in dots, like the score displays in the reference UI. Unknown characters are skipped. */
export const DotNumber: React.FC<{ value: string | number; size?: number; className?: string }> = (
  { value, size = 40, className },
) => {
  const text = String(value);
  const cell = size / 7;
  const dots: React.ReactNode[] = [];
  let x = 0;
  for (const ch of text) {
    const g = GLYPHS[ch];
    if (!g) continue;
    g.forEach((row, y) => [...row].forEach((c, i) => {
      if (c === "#") dots.push(<circle key={dots.length} cx={(x + i + 0.5) * cell} cy={(y + 0.5) * cell} r={cell * 0.34} />);
    }));
    x += g[0].length + 1;
  }
  return (
    <svg className={className} role="img" aria-label={text} width={Math.max(x - 1, 0) * cell} height={size}
      fill="currentColor">
      {dots}
    </svg>
  );
};
