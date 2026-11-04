import { Link } from "react-router-dom";

// Internal paths ("/app") navigate client-side without reloading the page; everything
// else ("#how", external URLs) stays a plain anchor.
export default function SmartLink({ href = "#", children, ...props }) {
  if (href.startsWith("/") && !href.startsWith("//")) {
    return (
      <Link to={href} {...props}>
        {children}
      </Link>
    );
  }
  return (
    <a href={href} {...props}>
      {children}
    </a>
  );
}
