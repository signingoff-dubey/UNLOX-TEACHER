import logoSvg from '../assets/rootlens-logo.svg?raw';

// The RootLens mark from the brand SVG: the hexagon lens over the root tree, one node lit orange (the fault).
// Classes and draw-order styles are stripped so it renders finished; the opening animation uses the same file.
const group = (cls) => logoSvg.match(new RegExp(`<g class="${cls}"[\\s\\S]*?</g>`))?.[0] ?? '';
const MARK = [group('hex'), group('roots'), group('nodes')].join('').replace(/ (class|style|pathLength)="[^"]*"/g, '');

const Logo = ({ size = 28, className = '' }) => (
  <span
    className={`grid shrink-0 place-items-center rounded-lg bg-[#171c20] ring-1 ring-white/10 ${className}`}
    style={{ width: size, height: size }}
    aria-hidden="true"
  >
    <svg viewBox="600 410 960 1030" width={Math.round(size * 0.78)} height={Math.round(size * 0.78)} dangerouslySetInnerHTML={{ __html: MARK }} />
  </span>
);

export default Logo;
