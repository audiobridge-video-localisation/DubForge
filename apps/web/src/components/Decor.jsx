import Draggable from "./ui/Draggable.jsx";
import { brand } from "../data/content.js";

// One small draggable desktop trinket, chosen by `item.type`.
export default function Decor({ item }) {
  const { type, x, y, rot } = item;
  return (
    <Draggable x={x} y={y} rot={rot}>
      {type === "tag" && (
        <div className={`tag ${item.tone}`}>
          <div className="hd">
            HELLO
            <br />
            my name is
          </div>
          <div className="nm">{brand}</div>
        </div>
      )}
      {type === "kao" && (
        <div className="kao" style={{ fontSize: item.size }}>
          {item.text}
        </div>
      )}
      {type === "folder" && <div className="folder" />}
      {type === "trash" && <div className="trash" />}
      {type === "beach" && <div className="beach" />}
    </Draggable>
  );
}
