const DIGITS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
const HEIGHT = 64; // keep in sync with .digit height in Pricing.css

// Each digit is a vertical strip of 0-9; changing the value just slides the strip.
export default function RollingNumber({ value }) {
  return (
    <span className="num">
      {String(value)
        .split("")
        .map((ch, i) => (
          <span key={i} className="digit">
            <span
              style={{ transform: `translateY(${-Number(ch) * HEIGHT}px)` }}
            >
              {DIGITS.map((n) => (
                <span key={n}>{n}</span>
              ))}
            </span>
          </span>
        ))}
    </span>
  );
}
