import { motion } from 'framer-motion';

// Springy enough to overshoot a little, like a drop of liquid settling.
export const LIQUID_SPRING = { type: 'spring', stiffness: 420, damping: 30, mass: 0.9 };

// The wobble a drop makes when it lands: stretched along the travel, then squashed, then round again.
const WOBBLE = {
  y: { scaleY: [1.18, 0.92, 1.03, 1], scaleX: [0.9, 1.05, 0.99, 1] },
  x: { scaleX: [1.18, 0.92, 1.03, 1], scaleY: [0.9, 1.05, 0.99, 1] },
  both: { scale: [0.86, 1.08, 0.98, 1] },
};

// A glass shape that glides to wherever it is rendered next. Render it inside the active item only: framer-motion
// animates it from the old item to the new one through the shared layoutId. The outer span carries the travel,
// the inner one the wobble, so the two transforms do not fight. The parent needs `position: relative`.
const Liquid = ({ layoutId, axis = 'y', className = '', fill = 'liquid-fill' }) => (
  <motion.span layoutId={layoutId} transition={LIQUID_SPRING} aria-hidden="true" className={`pointer-events-none absolute ${className}`}>
    <motion.span
      animate={WOBBLE[axis]}
      transition={{ duration: 0.55, ease: 'easeOut', times: [0, 0.35, 0.7, 1] }}
      className={`absolute inset-0 rounded-[inherit] ${fill}`}
    />
  </motion.span>
);

export default Liquid;
