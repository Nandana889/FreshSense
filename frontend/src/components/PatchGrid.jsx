/**
 * Decorative hero graphic: a leaf drawn on a 14 x 14 grid, which is how
 * ViT-Base-Patch16-224 divides a 224 x 224 image (16 x 16 px patches).
 * It illustrates that idea only and shows no model output.
 */
const GRID_SIZE = 14;
const CELL = 26;
const GAP = 3;
const VIEW_SIZE = GRID_SIZE * (CELL + GAP) - GAP;
const LEAF_LENGTH = 1.12;
const LEAF_WIDTH = 0.62;

/** Returns a 0-1 tone for a cell inside the leaf, or null for background. */
function leafTone(column, row) {
  // Map the cell to -1..1, then rotate 45 degrees so the leaf runs diagonally.
  const x = ((column + 0.5) / GRID_SIZE) * 2 - 1;
  const y = ((row + 0.5) / GRID_SIZE) * 2 - 1;
  const along = (x - y) * Math.SQRT1_2;
  const across = (x + y) * Math.SQRT1_2;

  const halfWidth = LEAF_WIDTH * (1 - (along / LEAF_LENGTH) ** 2);
  if (Math.abs(along) > LEAF_LENGTH || Math.abs(across) >= halfWidth) return null;

  // 0 along the central vein, rising to 1 at the leaf edge.
  return Math.abs(across) / halfWidth;
}

const CELLS = Array.from({ length: GRID_SIZE ** 2 }, (_, index) => {
  const column = index % GRID_SIZE;
  const row = Math.floor(index / GRID_SIZE);
  return { column, row, tone: leafTone(column, row) };
});

export default function PatchGrid() {
  return (
    <svg
      className="patch-grid"
      viewBox={`0 0 ${VIEW_SIZE} ${VIEW_SIZE}`}
      role="img"
      aria-label="A leaf illustrated as a 14 by 14 grid of image patches"
    >
      {CELLS.map(({ column, row, tone }) => (
        <rect
          key={`${column}-${row}`}
          className="patch"
          x={column * (CELL + GAP)}
          y={row * (CELL + GAP)}
          width={CELL}
          height={CELL}
          rx={5}
          style={{
            animationDelay: `${(column + row) * 22}ms`,
            ...(tone !== null && { fill: `hsl(146 ${48 + tone * 8}% ${48 - tone * 24}%)` }),
          }}
        />
      ))}
    </svg>
  );
}
