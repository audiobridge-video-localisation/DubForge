import Button from "./ui/Button.jsx";
import RollingNumber from "./RollingNumber.jsx";

export default function PlanCard({ plan, yearly }) {
  const price = yearly ? plan.yearly : plan.monthly;
  const note =
    plan.note ?? `per month, billed ${yearly ? "yearly" : "monthly"}`;
  return (
    <div className="plan">
      {plan.popular && <span className="badge">popular</span>}
      <h4>{plan.name}</h4>
      <p className="tag2">{plan.blurb}</p>
      <div className="price">
        <sup>$</sup>
        <RollingNumber value={price} />
      </div>
      <div className="per">{note}</div>
      <Button variant={plan.variant}>{plan.cta}</Button>
      <h5>includes</h5>
      <ul>
        {plan.includes.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
