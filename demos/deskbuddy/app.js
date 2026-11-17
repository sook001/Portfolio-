const elapsedLabel = document.getElementById("elapsed");
const stateLabel = document.getElementById("session-state");
const countdownLabel = document.getElementById("break-countdown");
const startButton = document.getElementById("start-session");
const pauseButton = document.getElementById("pause-session");
const finishButton = document.getElementById("finish-session");
const breakInterval = document.getElementById("break-interval");
const reminder = document.getElementById("reminder");
const reminderMessage = document.getElementById("reminder-message");
const reminderPauseButton = document.getElementById("reminder-pause");
const reminderCloseButton = document.getElementById("reminder-close");
const sessionsFinished = document.getElementById("sessions-finished");

let elapsedBeforeStart = 0;
let sessionStartedAt = 0;
let isRunning = false;
let nextBreakAt = Number(breakInterval.value) * 60;
let finishedCount = 0;
let reminderType = "routine";

function getElapsedSeconds() {
  if (!isRunning) {
    return elapsedBeforeStart;
  }
  return elapsedBeforeStart + Math.floor((Date.now() - sessionStartedAt) / 1000);
}

function formatTime(totalSeconds) {
  const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, "0");
  const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, "0");
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
}

function updateTimer() {
  const elapsed = getElapsedSeconds();
  const intervalSeconds = Number(breakInterval.value) * 60;
  elapsedLabel.textContent = formatTime(elapsed);
  startButton.disabled = isRunning;
  startButton.textContent = elapsed > 0 ? "เล่นต่อ" : "เริ่มเล่น";
  pauseButton.disabled = !isRunning;
  finishButton.disabled = elapsed === 0;
  stateLabel.textContent = isRunning ? "กำลังจับเวลา" : elapsed > 0 ? "พักชั่วคราว" : "พร้อมเริ่ม";
  countdownLabel.textContent = isRunning
    ? `เตือนพักใน ${formatTime(Math.max(0, nextBreakAt - elapsed))}`
    : "จับเวลาเฉพาะตอนกดเริ่มเล่น";

  if (isRunning && elapsed >= nextBreakAt && reminder.hidden) {
    nextBreakAt += intervalSeconds;
    showReminder("เล่นมานานแล้วนะ ลุกขึ้นยืดเส้นและพักสายตาสักครู่ไหม?", true);
  }
}

function showReminder(message, isBreak) {
  reminderType = isBreak ? "break" : "routine";
  reminderMessage.textContent = message;
  reminderPauseButton.hidden = !isBreak;
  reminderCloseButton.textContent = isBreak ? "เล่นต่อ" : "รับทราบ";
  reminder.hidden = false;
}

function closeReminder() {
  reminder.hidden = true;
  if (reminderType === "break" && isRunning) {
    nextBreakAt = getElapsedSeconds() + Number(breakInterval.value) * 60;
  }
}

startButton.addEventListener("click", () => {
  if (isRunning) {
    return;
  }
  sessionStartedAt = Date.now();
  isRunning = true;
  if (nextBreakAt <= elapsedBeforeStart) {
    nextBreakAt = elapsedBeforeStart + Number(breakInterval.value) * 60;
  }
  updateTimer();
});

pauseButton.addEventListener("click", () => {
  if (!isRunning) {
    return;
  }
  elapsedBeforeStart = getElapsedSeconds();
  isRunning = false;
  updateTimer();
});

finishButton.addEventListener("click", () => {
  if (getElapsedSeconds() > 0) {
    finishedCount += 1;
    sessionsFinished.textContent = String(finishedCount);
  }
  elapsedBeforeStart = 0;
  isRunning = false;
  nextBreakAt = Number(breakInterval.value) * 60;
  reminder.hidden = true;
  updateTimer();
});

breakInterval.addEventListener("change", () => {
  nextBreakAt = getElapsedSeconds() + Number(breakInterval.value) * 60;
  updateTimer();
});

document.getElementById("test-break").addEventListener("click", () => {
  showReminder("ลองพักสายตา ดื่มน้ำ หรือยืดเส้นสักนิดนะ", true);
});

document.getElementById("meal-reminder").addEventListener("click", () => {
  showReminder("ถึงเวลาพักไปหาอะไรอร่อย ๆ กินแล้วหรือยัง?", false);
});

document.getElementById("sleep-reminder").addEventListener("click", () => {
  showReminder("ดึกแล้วนะ พักผ่อนให้เพียงพอด้วยล่ะ", false);
});

reminderPauseButton.addEventListener("click", () => {
  if (isRunning) {
    elapsedBeforeStart = getElapsedSeconds();
    isRunning = false;
  }
  reminder.hidden = true;
  updateTimer();
});

reminderCloseButton.addEventListener("click", closeReminder);

window.setInterval(updateTimer, 1000);
updateTimer();
