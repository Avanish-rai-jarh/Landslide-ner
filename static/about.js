// ============================================================
// ABOUT PAGE — MOBILE NAVIGATION
// ============================================================

const menuButton = document.getElementById("menuBtn");
const mobileNavLinks = document.getElementById("navLinks");

if (menuButton && mobileNavLinks) {

    menuButton.addEventListener("click", function () {

        const isOpen = mobileNavLinks.classList.toggle("active");

        menuButton.textContent = isOpen ? "✕" : "☰";

        menuButton.setAttribute(
            "aria-expanded",
            String(isOpen)
        );

        menuButton.setAttribute(
            "aria-label",
            isOpen
                ? "Close navigation menu"
                : "Open navigation menu"
        );
    });

    mobileNavLinks
        .querySelectorAll("a")
        .forEach(function (link) {

            link.addEventListener("click", function () {

                mobileNavLinks.classList.remove("active");

                menuButton.textContent = "☰";

                menuButton.setAttribute(
                    "aria-expanded",
                    "false"
                );

                menuButton.setAttribute(
                    "aria-label",
                    "Open navigation menu"
                );
            });
        });
}