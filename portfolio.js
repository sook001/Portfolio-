document.querySelectorAll("[data-frame-image]").forEach((image) => {
  const frame = image.closest("[data-image-frame]");

  if (!frame) {
    throw new Error("Image frame is missing its data-image-frame container.");
  }

  const updateFrame = () => {
    const loaded = image.naturalWidth > 0;
    image.hidden = !loaded;
    frame.classList.toggle("has-image", loaded);
  };

  image.addEventListener("load", updateFrame);
  image.addEventListener("error", updateFrame);

  if (image.complete) {
    updateFrame();
  }
});

document.querySelectorAll("[data-preview-toggle]").forEach((button) => {
  const panel = document.getElementById(button.getAttribute("aria-controls"));

  if (!panel) {
    throw new Error(`Preview panel not found for ${button.getAttribute("aria-controls")}.`);
  }

  const iframe = panel.querySelector("iframe[data-preview-src]");

  if (!iframe) {
    throw new Error(`Preview iframe missing in ${panel.id}.`);
  }

  button.addEventListener("click", () => {
    const opening = button.getAttribute("aria-expanded") !== "true";
    button.setAttribute("aria-expanded", String(opening));
    button.textContent = opening ? button.dataset.closeLabel : button.dataset.openLabel;
    panel.hidden = !opening;

    if (opening) {
      if (!iframe.getAttribute("src")) {
        iframe.setAttribute("src", iframe.dataset.previewSrc);
      }
      panel.scrollIntoView({ block: "nearest" });
    } else {
      iframe.removeAttribute("src");
    }
  });
});

document.querySelectorAll("[data-copy-email]").forEach((button) => {
  const status = document.querySelector("[data-copy-status]");
  const toast = button.parentElement?.querySelector("[data-copy-toast]");
  const email = button.dataset.copyEmail;

  if (!status || !toast || !email) {
    throw new Error("Email copy button is missing its email or feedback elements.");
  }

  let dismissTimer;
  const showFeedback = (message, isError = false) => {
    window.clearTimeout(dismissTimer);
    status.textContent = message;
    toast.textContent = isError ? "คัดลอกไม่สำเร็จ" : "คัดลอกแล้ว";
    toast.dataset.state = isError ? "error" : "success";
    toast.classList.remove("is-visible");
    const buttonBounds = button.getBoundingClientRect();
    toast.style.left = `${buttonBounds.left + 8}px`;
    toast.style.top = `${buttonBounds.top - 8}px`;
    toast.style.setProperty("--toast-x-apex", `${-Math.min(toast.offsetWidth * 0.28, buttonBounds.width * 0.24)}px`);
    toast.style.setProperty("--toast-x-land", `${-(toast.offsetWidth * 0.4 + 16)}px`);
    toast.style.setProperty("--toast-y-apex", "-38px");
    toast.style.setProperty("--toast-y-land", `${window.innerHeight - (buttonBounds.top - 8) - toast.offsetHeight * 0.6}px`);
    toast.style.setProperty("--toast-y-exit", `${window.innerHeight - (buttonBounds.top - 8) + toast.offsetHeight + 24}px`);
    toast.getBoundingClientRect();
    toast.classList.add("is-visible");
    dismissTimer = window.setTimeout(() => {
      toast.classList.remove("is-visible");
    }, 1800);
  };

  button.addEventListener("click", async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(email);
      } else {
        const input = document.createElement("textarea");
        input.value = email;
        input.setAttribute("readonly", "");
        input.style.position = "fixed";
        input.style.opacity = "0";
        document.body.append(input);
        let copied;
        try {
          input.select();
          copied = document.execCommand("copy");
        } finally {
          input.remove();
        }

        if (!copied) {
          throw new Error("Clipboard copy command was rejected.");
        }
      }

      showFeedback("คัดลอกอีเมลแล้ว");
    } catch (error) {
      showFeedback("คัดลอกไม่สำเร็จ กรุณาคัดลอกอีเมลด้วยตนเอง", true);
      console.error("Could not copy the contact email.", error);
    }
  });
});
