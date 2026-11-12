import { brand, builtWith, footerColumns } from "../data/content.js";
import SmartLink from "./ui/SmartLink.jsx";
import "./Footer.css";

export default function Footer() {
  return (
    <footer className="footer">
      <div className="fcols">
        {footerColumns.map((col) => (
          <div key={col.title}>
            <h6>{col.title}</h6>
            {col.links.map(([label, href]) => (
              <SmartLink key={label} href={href}>
                {label}
              </SmartLink>
            ))}
          </div>
        ))}
        <div>
          <h6>built with</h6>
          <ul className="built">
            {builtWith.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
        </div>
        <div>
          <h6>status</h6>
          <p>
            early access. no accounts, plans or public pricing yet, and the
            supported languages are English to Hindi and Bengali.
          </p>
        </div>
      </div>
      <div className="wordmark">{brand}</div>
      <div className="copy-line">© 2026 {brand}</div>
    </footer>
  );
}
