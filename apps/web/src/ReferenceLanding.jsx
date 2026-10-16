import MenuBar from "./components/MenuBar.jsx";
import Hero from "./components/Hero.jsx";
import Features from "./components/Features.jsx";
import Manifesto from "./components/Manifesto.jsx";
import Feedback from "./components/Feedback.jsx";
import Pricing from "./components/Pricing.jsx";
import Faq from "./components/Faq.jsx";
import Footer from "./components/Footer.jsx";

export default function App() {
  return (
    <>
      <MenuBar />
      <main>
        <Hero />
        <Features />
        <Manifesto />
        <Feedback />
        <Pricing />
        <Faq />
      </main>
      <Footer />
    </>
  );
}
