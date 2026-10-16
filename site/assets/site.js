"use strict";

document.documentElement.classList.add("js");

const menu = document.querySelector(".nav-toggle");
const navigation = document.querySelector("#site-nav");

if (menu && navigation) {
  menu.hidden = false;
  navigation.dataset.open = "false";
  const setMenu = (open) => {
    menu.setAttribute("aria-expanded", String(open));
    navigation.dataset.open = String(open);
  };
  menu.addEventListener("click", () => setMenu(menu.getAttribute("aria-expanded") !== "true"));
  navigation.addEventListener("click", (event) => {
    if (event.target.closest("a")) setMenu(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && menu.getAttribute("aria-expanded") === "true") {
      setMenu(false);
      menu.focus();
    }
  });
}

const filters = document.querySelector(".project-filters");
const projects = [...document.querySelectorAll(".project[data-category]")];
const count = document.querySelector("#project-count");

if (filters && count) {
  filters.hidden = false;
  filters.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-filter]");
    if (!button) return;
    for (const candidate of filters.querySelectorAll("button")) {
      candidate.setAttribute("aria-pressed", String(candidate === button));
    }
    for (const project of projects) {
      project.hidden = button.dataset.filter !== "all" && project.dataset.category !== button.dataset.filter;
    }
    const visible = projects.filter((project) => !project.hidden).length;
    count.textContent = `${visible} ${visible === 1 ? "project" : "projects"}`;
  });
}

const copy = document.querySelector("#copy-command");
const command = document.querySelector("#replay-command");
const copyStatus = document.querySelector("#copy-status");

if (copy && command && copyStatus) {
  copy.hidden = false;
  copy.addEventListener("click", async () => {
    if (!navigator.clipboard) {
      copyStatus.textContent = "Copy is unavailable here. Select and copy the command above.";
      return;
    }
    try {
      await navigator.clipboard.writeText(command.textContent);
      copyStatus.textContent = "Command copied.";
    } catch (error) {
      console.error("Unable to copy replay command:", error);
      copyStatus.textContent = "Could not copy. Select and copy the command above.";
    }
  });
}
