import SmartLink from "./SmartLink.jsx";
import "./Button.css";

export default function Button({
  variant = "secondary",
  icon,
  children,
  ...props
}) {
  return (
    <SmartLink className={`btn ${variant}`} {...props}>
      {icon}
      {children}
    </SmartLink>
  );
}
