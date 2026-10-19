// Title-bar tint and avatar colour are derived from the card's index.
const TINTS = ["tint-a", "tint-b", "tint-c", "tint-d"];

export default function TestimonialCard({ item, index }) {
  const hue = (index * 47) % 360;
  const avatar = `linear-gradient(135deg, hsl(${hue} 70% 70%), hsl(${(hue + 60) % 360} 70% 55%))`;
  return (
    <div className={`card ${TINTS[index % 4]}`}>
      <div className="tb">
        <b />
        <b />
        <b />
      </div>
      <div className="bd">
        <div className="who">
          <div className="av" style={{ background: avatar }} />
          <div>
            <strong>{item.name}</strong>
            <span>{item.handle}</span>
          </div>
        </div>
        <p>{item.text}</p>
        <small>{item.date}</small>
      </div>
    </div>
  );
}
