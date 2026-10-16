import "./Button.css";

export default function Button({
  variant = "secondary",
  icon,
  children,
  ...props
}) {
  return (
    <a className={`btn ${variant}`} href="#" {...props}>
      {icon}
      {children}
    </a>
  );
}
