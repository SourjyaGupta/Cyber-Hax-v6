const LIVE_GAME_PATH = "/play/";

document.querySelectorAll("[data-live-game-link]").forEach((link) => {
  link.setAttribute("href", LIVE_GAME_PATH);
});

const yearNode = document.getElementById("footerYear");
if (yearNode) {
  yearNode.textContent = `(c) ${new Date().getFullYear()} Cyber Hax v5`;
}

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) entry.target.classList.add("is-visible");
    });
  },
  {
    threshold: 0.15,
  },
);

document.querySelectorAll(".reveal").forEach((node) => observer.observe(node));
