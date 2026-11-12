import MenuBar from "./components/MenuBar.jsx";
import Hero from "./components/Hero.jsx";
import Pipeline from "./components/Pipeline.jsx";
import ReviewPass from "./components/ReviewPass.jsx";
import Statement from "./components/Statement.jsx";
import EarlyAccess from "./components/EarlyAccess.jsx";
import Faq from "./components/Faq.jsx";
import Footer from "./components/Footer.jsx";

export default function App() {
  return (
    <div className="landing">
      <MenuBar />
      <main>
        <Hero />
        <Pipeline />
        <ReviewPass />
        <Statement />
        <EarlyAccess />
        <Faq />
      </main>
      <Footer />
    </div>
  );
}
