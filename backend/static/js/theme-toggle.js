// Global Theme Switcher (Modo Claro / Modo Oscuro)
(function() {
  const savedTheme = localStorage.getItem("app_theme") || "dark";
  if (savedTheme === "light") {
    document.body.classList.add("light-theme");
  } else {
    document.body.classList.remove("light-theme");
  }
})();

function toggleThemeMode() {
  const isLight = document.body.classList.contains("light-theme");
  if (isLight) {
    document.body.classList.remove("light-theme");
    localStorage.setItem("app_theme", "dark");
  } else {
    document.body.classList.add("light-theme");
    localStorage.setItem("app_theme", "light");
  }
  const activeTheme = isLight ? "oscuro" : "blanco";
  const msg = `Tema ${activeTheme} activado`;
  if (typeof syncThemeToggleButtons === "function") syncThemeToggleButtons();
  if (typeof showToast === "function") {
    showToast(msg, "info");
  } else {
    console.log(msg);
  }
}

function syncThemeToggleButtons() {
  const isLight = document.body.classList.contains("light-theme");
  const targetTheme = isLight ? "oscuro" : "blanco";
  const targetLabel = isLight ? "OSCURO" : "BLANCO";
  const icon = isLight ? "🌙" : "☀️";

  document.querySelectorAll(".theme-toggle-btn, .theme-mode-drawer-toggle").forEach(button => {
    button.setAttribute("aria-label", `Cambiar a tema ${targetTheme}`);
    button.setAttribute("title", `Cambiar a tema ${targetTheme}`);
    button.innerHTML = `<span aria-hidden="true">${icon}</span><span>${targetLabel}</span>`;
  });
}

document.addEventListener("DOMContentLoaded", syncThemeToggleButtons);
