import { useEffect, useState } from "react";

const format = () =>
  new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

export default function useClock() {
  const [time, setTime] = useState(format);
  useEffect(() => {
    const id = setInterval(() => setTime(format()), 10000);
    return () => clearInterval(id);
  }, []);
  return time;
}
