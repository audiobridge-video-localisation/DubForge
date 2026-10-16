import { brand, footerColumns } from "../data/content.js";
import "./Footer.css";

export default function Footer() {
  return (
    <footer className="footer">
      <div className="fcols">
        {footerColumns.map((col) => (
          <div key={col.title}>
            <h6>{col.title}</h6>
            {col.links.map(([label, href]) => (
              <a key={label} href={href}>
                {label}
              </a>
            ))}
          </div>
        ))}
        <div>
          <h6>disclaimer</h6>
          <p>
            *{brand} only sees your screen when you press the hotkey.
            screenshots are never stored.
          </p>
        </div>
      </div>
      <div className="wordmark">{brand}</div>
      <div className="copy-line">© Your Company, Inc.</div>
    </footer>
  );
}
