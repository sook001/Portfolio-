const roster = Array.from({ length: 12 }, (_, index) => {
  const number = String(index + 1).padStart(2, "0");
  return {
    id: `650000${String(index + 1).padStart(2, "0")}`,
    name: `นักศึกษาตัวอย่าง ${number}`,
  };
});

const weeklyCounts = new Map(
  roster.map((student, index) => [
    student.id,
    { present: 4 + (index % 4), late: index % 2, absent: (index + 1) % 3 },
  ]),
);

const todayLogs = new Map();
const sampleEntries = [
  { studentIndex: 0, status: "มาตรง", time: "08:10:00" },
  { studentIndex: 3, status: "มาสาย", time: "08:23:00" },
  { studentIndex: 6, status: "มาตรง", time: "08:31:00" },
];

const statusClass = { มาตรง: "present", มาสาย: "late", ขาด: "absent" };
const statusCountKey = { มาตรง: "present", มาสาย: "late", ขาด: "absent" };
const thaiMonths = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."];
let selectedStudent = null;

const rosterGrid = document.getElementById("rosterGrid");
const rosterSearch = document.getElementById("rosterSearch");
const selectedRow = document.getElementById("selectedRow");
const selectedLabel = document.getElementById("selectedLabel");
const stampButtons = document.querySelectorAll(".stamp-btn");
const formMessage = document.getElementById("formMsg");
const logList = document.getElementById("logList");
const statsBody = document.getElementById("statsBody");
const statsSearch = document.getElementById("statsSearch");
const statsSummary = document.getElementById("statsSummary");
const inkStamp = document.getElementById("inkStamp");
const inkStampMark = document.getElementById("inkStampMark");

for (const entry of sampleEntries) {
  const student = roster[entry.studentIndex];
  todayLogs.set(student.id, { ...entry, studentId: student.id });
  weeklyCounts.get(student.id)[statusCountKey[entry.status]] += 1;
}

function renderClock() {
  const now = new Date();
  document.getElementById("clockTime").textContent = now.toLocaleTimeString("th-TH", { hour12: false });
  document.getElementById("clockDate").textContent =
    `${now.getDate()} ${thaiMonths[now.getMonth()]} ${now.getFullYear() + 543}`;
}

function setSelectedStudent(student) {
  selectedStudent = student;
  selectedLabel.textContent = student ? `${student.id} — ${student.name}` : "ยังไม่ได้เลือกนักศึกษา";
  selectedRow.classList.toggle("has-student", Boolean(student));
  stampButtons.forEach((button) => {
    button.disabled = !student;
  });
  renderRoster();
}

function renderRoster() {
  const query = rosterSearch.value.trim().toLocaleLowerCase("th");
  const visibleRoster = roster.filter((student) =>
    student.id.toLocaleLowerCase("th").includes(query) ||
    student.name.toLocaleLowerCase("th").includes(query),
  );
  rosterGrid.replaceChildren();

  if (!visibleRoster.length) {
    const empty = document.createElement("div");
    empty.className = "feed-empty";
    empty.textContent = "ไม่พบนักศึกษาตัวอย่างที่ตรงกับคำค้นหา";
    rosterGrid.append(empty);
    return;
  }

  for (const student of visibleRoster) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `roster-item${selectedStudent?.id === student.id ? " selected" : ""}`;
    button.setAttribute("role", "option");
    button.setAttribute("aria-selected", String(selectedStudent?.id === student.id));

    const name = document.createElement("span");
    name.className = "r-name";
    name.textContent = student.name;
    const id = document.createElement("span");
    id.className = "r-id";
    id.textContent = student.id;
    button.append(name, id);
    button.addEventListener("click", () => {
      formMessage.textContent = "";
      formMessage.classList.remove("ok");
      setSelectedStudent(student);
    });
    rosterGrid.append(button);
  }
}

function renderLogs() {
  logList.replaceChildren();
  const entries = [...todayLogs.values()].sort((left, right) => right.time.localeCompare(left.time));

  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "feed-empty";
    empty.textContent = "ยังไม่มีการเช็คชื่อในเดโมนี้";
    logList.append(empty);
    return;
  }

  for (const entry of entries) {
    const student = roster.find((item) => item.id === entry.studentId);
    const row = document.createElement("div");
    row.className = "log-row";
    for (const [className, text] of [
      ["log-id", entry.studentId],
      ["log-name", student.name],
      [`log-status ${statusClass[entry.status]}`, entry.status],
      ["log-time", entry.time],
    ]) {
      const cell = document.createElement("span");
      cell.className = className;
      cell.textContent = text;
      row.append(cell);
    }
    logList.append(row);
  }
}

function renderStats() {
  const query = statsSearch.value.trim().toLocaleLowerCase("th");
  const filteredRoster = roster.filter((student) =>
    student.id.toLocaleLowerCase("th").includes(query) ||
    student.name.toLocaleLowerCase("th").includes(query),
  );
  statsBody.replaceChildren();

  if (!filteredRoster.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.className = "stats-empty";
    cell.textContent = "ไม่พบข้อมูลตัวอย่าง";
    row.append(cell);
    statsBody.append(row);
  }

  for (const student of filteredRoster) {
    const counts = weeklyCounts.get(student.id);
    const total = counts.present + counts.late + counts.absent;
    const rate = total ? Math.round(((counts.present + counts.late) / total) * 100) : null;
    const row = document.createElement("tr");
    const values = [
      ["st-id", student.id],
      ["st-name", student.name],
      ["st-num present", String(counts.present)],
      ["st-num late", String(counts.late)],
      ["st-num absent", String(counts.absent)],
      ["st-rate", rate === null ? "—" : `${rate}%`],
    ];

    for (const [className, text] of values) {
      const cell = document.createElement("td");
      cell.className = className;
      cell.textContent = text;
      row.append(cell);
    }
    statsBody.append(row);
  }

  const totals = [...weeklyCounts.values()].reduce(
    (sum, counts) => ({
      present: sum.present + counts.present,
      late: sum.late + counts.late,
      absent: sum.absent + counts.absent,
    }),
    { present: 0, late: 0, absent: 0 },
  );
  statsSummary.textContent =
    `ข้อมูลตัวอย่างรวม: มาตรง ${totals.present} · มาสาย ${totals.late} · ขาด ${totals.absent}`;
}

function playStamp(status) {
  inkStampMark.textContent = status;
  inkStampMark.style.color = `var(--stamp-${statusClass[status] === "present" ? "green" : statusClass[status] === "late" ? "red" : "slate"})`;
  inkStamp.classList.remove("play");
  void inkStamp.offsetWidth;
  inkStamp.classList.add("play");
}

function saveStatus(status) {
  if (!selectedStudent) {
    return;
  }

  const existing = todayLogs.get(selectedStudent.id);
  if (existing?.status === status) {
    formMessage.textContent = `ข้อมูลตัวอย่างบันทึก "${status}" ไว้แล้ว`;
    formMessage.classList.add("ok");
    return;
  }

  const counts = weeklyCounts.get(selectedStudent.id);
  if (existing) {
    counts[statusCountKey[existing.status]] -= 1;
  }
  counts[statusCountKey[status]] += 1;
  todayLogs.set(selectedStudent.id, {
    studentId: selectedStudent.id,
    status,
    time: new Date().toLocaleTimeString("th-TH", { hour12: false }),
  });

  playStamp(status);
  formMessage.textContent = `เดโมบันทึก "${status}" ให้ ${selectedStudent.name} แล้ว (ในหน้านี้เท่านั้น)`;
  formMessage.classList.add("ok");
  setSelectedStudent(null);
  renderLogs();
  renderStats();
}

stampButtons.forEach((button) => {
  button.addEventListener("click", () => saveStatus(button.dataset.status));
});

rosterSearch.addEventListener("input", renderRoster);
statsSearch.addEventListener("input", renderStats);

renderClock();
renderRoster();
renderLogs();
renderStats();
window.setInterval(renderClock, 1000);
