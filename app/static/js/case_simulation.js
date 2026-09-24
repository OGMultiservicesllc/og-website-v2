/* Case Simulation working screen — document viewer (image/PDF, Prev/Next,
   Close) and a light client-side check that every multi-select task has at
   least one option checked before submit (everything else uses plain HTML5
   `required`). No editor, no zoom engine of our own — images/PDFs render via
   the browser's own viewer, which already supports pinch/scroll zoom. */
(function () {
    "use strict";
    var docs = window.OG_CASE_DOCUMENTS || [];
    var viewer = document.getElementById("case-doc-viewer");
    var titleEl = document.getElementById("case-doc-viewer-title");
    var imgEl = document.getElementById("case-doc-image");
    var pdfEl = document.getElementById("case-doc-pdf");
    var counterEl = document.getElementById("case-doc-counter");
    var prevBtn = document.getElementById("case-doc-prev");
    var nextBtn = document.getElementById("case-doc-next");
    var closeBtn = document.getElementById("case-doc-close");

    var currentIndex = 0;

    function render() {
        if (!docs.length) return;
        var doc = docs[currentIndex];
        titleEl.textContent = doc.label;
        counterEl.textContent = (currentIndex + 1) + " / " + docs.length;
        prevBtn.disabled = currentIndex === 0;
        nextBtn.disabled = currentIndex === docs.length - 1;

        if (doc.isPdf) {
            pdfEl.src = doc.url;
            pdfEl.classList.remove("hidden");
            imgEl.classList.add("hidden");
            imgEl.removeAttribute("src");
        } else {
            imgEl.src = doc.url;
            imgEl.classList.remove("hidden");
            pdfEl.classList.add("hidden");
            pdfEl.removeAttribute("src");
        }
    }

    function openViewer(index) {
        currentIndex = index;
        render();
        viewer.classList.remove("hidden");
        document.body.style.overflow = "hidden";
    }

    function closeViewer() {
        viewer.classList.add("hidden");
        pdfEl.removeAttribute("src");
        imgEl.removeAttribute("src");
        document.body.style.overflow = "";
    }

    document.querySelectorAll(".case-doc-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            openViewer(parseInt(btn.getAttribute("data-index"), 10));
        });
    });
    closeBtn.addEventListener("click", closeViewer);
    prevBtn.addEventListener("click", function () { if (currentIndex > 0) { currentIndex--; render(); } });
    nextBtn.addEventListener("click", function () { if (currentIndex < docs.length - 1) { currentIndex++; render(); } });
    viewer.addEventListener("click", function (e) { if (e.target === viewer) closeViewer(); });

    // ---------------------------------------------------------------- multi-select validation
    var form = document.getElementById("case-form");
    if (form && form.dataset.preview !== "true") {
        form.addEventListener("submit", function (e) {
            var groups = document.querySelectorAll(".multi-select-group");
            for (var i = 0; i < groups.length; i++) {
                var checked = groups[i].querySelectorAll("input[type=checkbox]:checked");
                if (checked.length === 0) {
                    e.preventDefault();
                    groups[i].scrollIntoView({ behavior: "smooth", block: "center" });
                    alert(window.OG_CASE_I18N.selectAllRequired);
                    return;
                }
            }
        });
    }
})();
