const sectionLinks = document.querySelectorAll("[data-section-link]");
const navigableSections = document.querySelectorAll("main .section[id]");

if ("IntersectionObserver" in window) {
  const sectionObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) {
        return;
      }

      sectionLinks.forEach((link) => {
        if (link.getAttribute("href") === `#${entry.target.id}`) {
          link.setAttribute("aria-current", "location");
        } else {
          link.removeAttribute("aria-current");
        }
      });
    });
  }, { rootMargin: "-30% 0px -60% 0px" });

  navigableSections.forEach((section) => sectionObserver.observe(section));
}

if (
  "IntersectionObserver" in window
  && !window.matchMedia("(prefers-reduced-motion: reduce)").matches
) {
  document.documentElement.classList.add("has-reveal");
  const revealObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });

  document.querySelectorAll(".reveal").forEach((element) => revealObserver.observe(element));
}

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

document.querySelectorAll("[data-video-player]").forEach((player) => {
  const video = player.querySelector("[data-video]");
  const title = player.querySelector("[data-video-title]");
  const counter = player.querySelector("[data-video-counter]");
  const dotsContainer = player.querySelector("[data-video-dots]");
  const previousButton = player.querySelector("[data-video-prev]");
  const nextButton = player.querySelector("[data-video-next]");
  const muteButton = player.querySelector("[data-video-mute]");
  const playButton = player.querySelector("[data-video-play]");

  if (!video || !title || !counter || !dotsContainer || !previousButton || !nextButton || !muteButton || !playButton) {
    throw new Error("Video player is missing required controls.");
  }

  const playlist = [
    { title: "Tenshi Akuma Final", src: "Video/Video/Tenshi Akuma Final.mp4" },
    { title: "NanarisComplete", src: "Video/Video/NanarisComplete.mp4" },
    { title: "Nana 3D Model", src: "Video/Video/Nana 3D Model.mp4" },
    { title: "Nan Final hero", src: "Video/Video/Nan Final hero.mp4" },
  ];

  let currentIndex = 0;
  let loadTimer;
  video.muted = false;

  const updateMuteControl = () => {
    muteButton.textContent = video.muted ? "เสียงปิด" : "เสียงเปิด";
    muteButton.setAttribute("aria-label", video.muted ? "เปิดเสียง" : "ปิดเสียง");
  };
  updateMuteControl();

  const dots = playlist.map((item, index) => {
    const dot = document.createElement("button");
    dot.type = "button";
    dot.className = "hobby-player__dot";
    dot.setAttribute("aria-label", `เปิดวิดีโอ ${item.title}`);
    dot.addEventListener("click", () => showVideo(index));
    dotsContainer.append(dot);
    return dot;
  });

  const playCurrentVideo = () => {
    const playPromise = video.play();
    if (playPromise !== undefined) {
      playPromise.catch(() => {
        video.controls = false;
      });
    }
  };

  const showVideo = (index) => {
    window.clearTimeout(loadTimer);
    currentIndex = (index + playlist.length) % playlist.length;
    const item = playlist[currentIndex];

    video.pause();
    video.muted = false;
    updateMuteControl();
    video.innerHTML = "";
    const source = document.createElement("source");
    source.src = item.src;
    source.type = "video/mp4";
    video.append(source);
    video.load();

    title.textContent = item.title;
    counter.textContent = `${String(currentIndex + 1).padStart(2, "0")} / ${String(playlist.length).padStart(2, "0")}`;
    dots.forEach((dot, dotIndex) => {
      dot.classList.toggle("is-active", dotIndex === currentIndex);
      dot.setAttribute("aria-current", dotIndex === currentIndex ? "true" : "false");
    });

    loadTimer = window.setTimeout(playCurrentVideo, 100);
  };

  previousButton.addEventListener("click", () => showVideo(currentIndex - 1));
  nextButton.addEventListener("click", () => showVideo(currentIndex + 1));
  video.addEventListener("ended", () => showVideo(currentIndex + 1));
  video.addEventListener("error", () => {
    window.clearTimeout(loadTimer);
    loadTimer = window.setTimeout(() => showVideo(currentIndex + 1), 1500);
  });

  muteButton.addEventListener("click", () => {
    video.muted = !video.muted;
    updateMuteControl();
  });

  playButton.addEventListener("click", () => {
    if (video.paused) {
      playCurrentVideo();
    } else {
      video.pause();
    }
  });

  video.addEventListener("play", () => {
    playButton.textContent = "II";
    playButton.setAttribute("aria-label", "หยุดวิดีโอ");
  });

  video.addEventListener("pause", () => {
    playButton.textContent = "▶";
    playButton.setAttribute("aria-label", "เล่นวิดีโอ");
  });

  dots.forEach((dot, dotIndex) => {
    dot.classList.toggle("is-active", dotIndex === 0);
  });

  const observer = new IntersectionObserver((entries) => {
    if (entries[0]?.isIntersecting) {
      playCurrentVideo();
    } else {
      video.pause();
    }
  }, { threshold: 0.45 });

  observer.observe(player);
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
