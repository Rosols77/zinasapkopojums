(function () {
    const root = document.documentElement;
    const storageKey = "newsZoomPercent";
    const minPercent = 80;
    const maxPercent = 220;
    const stepPercent = 10;
    const defaultPercent = 110;

    function clampPercent(value) {
        const parsed = Number(String(value).replace("%", "").trim());
        if (!Number.isFinite(parsed)) return defaultPercent;
        return Math.min(maxPercent, Math.max(minPercent, parsed));
    }

    function setZoom(percentValue) {
        const percent = Math.round(clampPercent(percentValue));
        const scale = percent / 100;
        // Spacing grows slower than text/images, so margins do not become strange at high zoom.
        const spaceScale = 0.9 + (scale - 1) * 0.45;

        root.style.setProperty("--news-zoom", scale.toFixed(2));
        root.style.setProperty("--news-space", Math.max(0.8, Math.min(1.55, spaceScale)).toFixed(2));
        localStorage.setItem(storageKey, String(percent));

        document.querySelectorAll("[data-news-zoom-label]").forEach((label) => {
            label.textContent = percent + "%";
        });
        document.querySelectorAll("[data-news-zoom-slider]").forEach((slider) => {
            slider.value = String(percent);
            slider.setAttribute("aria-valuenow", String(percent));
        });
        document.querySelectorAll("[data-news-zoom-input]").forEach((input) => {
            input.value = percent + "%";
        });

        window.dispatchEvent(new Event("newszoomchange"));
    }

    function getCurrentPercent() {
        return clampPercent(localStorage.getItem(storageKey) || defaultPercent);
    }

    function setupSummaryToggles() {
        document.querySelectorAll("[data-summary-wrap]").forEach((wrap) => {
            const text = wrap.querySelector("[data-summary-text]");
            const toggle = wrap.querySelector("[data-summary-toggle]");
            if (!text || !toggle) return;

            const expanded = wrap.classList.contains("is-expanded");
            toggle.hidden = false;
            if (!expanded) {
                // Hide button only when summary truly fits inside the clamp.
                toggle.hidden = text.scrollHeight <= text.clientHeight + 6;
                toggle.textContent = "Lasīt vairāk";
            } else {
                toggle.textContent = "Rādīt mazāk";
            }

            if (toggle.dataset.bound === "1") return;
            toggle.dataset.bound = "1";
            toggle.addEventListener("click", () => {
                const isExpanded = wrap.classList.toggle("is-expanded");
                toggle.textContent = isExpanded ? "Rādīt mazāk" : "Lasīt vairāk";
            });
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        setZoom(getCurrentPercent());
        setupSummaryToggles();

        document.querySelectorAll("[data-news-zoom]").forEach((button) => {
            button.addEventListener("click", function () {
                const current = getCurrentPercent();
                const action = button.getAttribute("data-news-zoom");
                if (action === "in") setZoom(current + stepPercent);
                if (action === "out") setZoom(current - stepPercent);
                if (action === "reset") setZoom(defaultPercent);
                setTimeout(setupSummaryToggles, 80);
            });
        });

        document.querySelectorAll("[data-news-zoom-slider]").forEach((slider) => {
            slider.addEventListener("input", function () {
                setZoom(slider.value);
                setTimeout(setupSummaryToggles, 80);
            });
        });

        document.querySelectorAll("[data-news-zoom-input]").forEach((input) => {
            function applyInput() {
                setZoom(input.value);
                setTimeout(setupSummaryToggles, 80);
            }
            input.addEventListener("change", applyInput);
            input.addEventListener("blur", applyInput);
            input.addEventListener("keydown", (event) => {
                if (event.key === "Enter") {
                    event.preventDefault();
                    applyInput();
                }
            });
        });

        window.addEventListener("newszoomchange", () => setTimeout(setupSummaryToggles, 80));
    });
})();
