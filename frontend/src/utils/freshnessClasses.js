import { CircleAlert, CircleCheck, CircleX, CircleHelp } from 'lucide-react';

/**
 * Display settings for each backend class name. Every class pairs a colour
 * with its own icon, so the result never depends on colour alone.
 */
const FRESHNESS_CLASSES = {
  Fresh: { tone: 'fresh', Icon: CircleCheck },
  Mildly_Spoiled: { tone: 'mild', Icon: CircleAlert },
  Spoiled: { tone: 'spoiled', Icon: CircleX },
};

const UNKNOWN_CLASS = { tone: 'unknown', Icon: CircleHelp };

export const getClassStyle = (className) => FRESHNESS_CLASSES[className] ?? UNKNOWN_CLASS;

/** "Mildly_Spoiled" -> "Mildly Spoiled" */
export const formatClassName = (className) => className.replaceAll('_', ' ');
