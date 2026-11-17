// -----------------------------------------------------------------------
// script.js
// เชื่อมต่อกับ Firebase (Firestore) สำหรับหน้าเช็คชื่อเข้าเรียน IT401
// -----------------------------------------------------------------------

import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAnalytics } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-analytics.js";
import {
  getFirestore, collection, doc, setDoc, getDoc, getDocs,
  query, where, orderBy, limit, onSnapshot, serverTimestamp, Timestamp,
  increment
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import { firebaseConfig } from "./firebase-config.js";

const app = initializeApp(firebaseConfig);

// Analytics ใช้งานได้เฉพาะตอนรันผ่าน http/https จริง (ไม่ทำงานถ้าเปิดไฟล์ตรง ๆ แบบ file://)
try {
  getAnalytics(app);
} catch (err) {
  console.warn("Analytics ไม่ทำงานในสภาพแวดล้อมนี้:", err.message);
}

const db = getFirestore(app);

// -----------------------------------------------------------------------
// Utilities
// -----------------------------------------------------------------------

// ป้องกัน XSS: escape ค่าใด ๆ ที่จะแทรกลงใน innerHTML
function escapeHtml(str){
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[c]));
}

function getDateKey(date = new Date()){
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function startOfToday(){
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

// ฟังก์ชันหาเลขสัปดาห์ปัจจุบัน
function getWeekKey(date = new Date()) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
  return `Week${weekNo}`;
}

// -----------------------------------------------------------------------
// นาฬิกาบนหัวข้อ
// -----------------------------------------------------------------------
const clockTimeEl = document.getElementById("clockTime");
const clockDateEl = document.getElementById("clockDate");
const THAI_MONTHS = ["ม.ค.","ก.พ.","มี.ค.","เม.ย.","พ.ค.","มิ.ย.","ก.ค.","ส.ค.","ก.ย.","ต.ค.","พ.ย.","ธ.ค."];

function renderClock(){
  const now = new Date();
  clockTimeEl.textContent = now.toLocaleTimeString("th-TH", { hour12:false });
  clockDateEl.textContent = `${now.getDate()} ${THAI_MONTHS[now.getMonth()]} ${now.getFullYear()+543}`;
}
renderClock();
setInterval(renderClock, 1000);

// -----------------------------------------------------------------------
// สถานะการเลือกนักศึกษา
// -----------------------------------------------------------------------
let selectedStudent = null; // { id, name }

const selectedRow = document.getElementById("selectedRow");
const selectedLabel = document.getElementById("selectedLabel");
const stampButtons = document.querySelectorAll(".stamp-btn");
const formMsg = document.getElementById("formMsg");

function setSelectedStudent(student){
  selectedStudent = student;
  if (student){
    selectedLabel.textContent = `${student.id} — ${student.name}`;
    selectedRow.classList.add("has-student");
  } else {
    selectedLabel.textContent = "ยังไม่ได้เลือกนักศึกษา";
    selectedRow.classList.remove("has-student");
  }
  stampButtons.forEach(btn => { btn.disabled = !student; });
}

function clearMsg(){
  formMsg.textContent = "";
  formMsg.classList.remove("ok");
}

// -----------------------------------------------------------------------
// โหลดรายชื่อนักศึกษาทั้งหมด (ใช้ทั้งสำหรับ roster grid, cache ชื่อในฟีด, และสถิติ)
// -----------------------------------------------------------------------
const studentNameCache = new Map();
let roster = []; // [{ id, name }]

async function loadRoster(){
  try {
    const snap = await getDocs(collection(db, "student_IT401"));
    roster = snap.docs.map(d => {
      const data = d.data();
      const name = data.name || "(ไม่มีชื่อ)";
      studentNameCache.set(d.id, name);
      return { id: String(d.id), name }; // บังคับให้ Document ID เป็น String เสมอ
    }).sort((a, b) => a.id.localeCompare(b.id, "th"));
    renderRoster(roster);
  } catch (err) {
    console.error("โหลดรายชื่อนักศึกษาไม่สำเร็จ:", err);
    rosterGrid.innerHTML = `<div class="feed-empty">โหลดรายชื่อไม่สำเร็จ ตรวจสอบการเชื่อมต่อ Firebase</div>`;
  }
}

async function fetchStudentName(studentId){
  if (studentNameCache.has(studentId)) return studentNameCache.get(studentId);
  try {
    const snap = await getDoc(doc(db, "student_IT401", String(studentId)));
    const name = snap.exists() ? snap.data().name : null;
    studentNameCache.set(studentId, name);
    return name;
  } catch (err) {
    console.error("อ่านข้อมูลนักศึกษาไม่สำเร็จ:", err);
    return null;
  }
}

// -----------------------------------------------------------------------
// Roster grid (เลือกนักศึกษาจากรายชื่อ)
// -----------------------------------------------------------------------
const rosterGrid = document.getElementById("rosterGrid");
const rosterSearch = document.getElementById("rosterSearch");

function renderRoster(list){
  if (!list.length){
    rosterGrid.innerHTML = `<div class="feed-empty">ไม่พบนักศึกษาที่ตรงกับคำค้นหา</div>`;
    return;
  }
  rosterGrid.innerHTML = list.map(s => `
    <button type="button" class="roster-item${selectedStudent && selectedStudent.id === s.id ? " selected" : ""}"
      data-id="${escapeHtml(s.id)}" role="option" aria-selected="${selectedStudent && selectedStudent.id === s.id}">
      <span class="r-name">${escapeHtml(s.name)}</span>
      <span class="r-id">${escapeHtml(s.id)}</span>
    </button>
  `).join("");
}

rosterGrid.addEventListener("click", (e) => {
  const btn = e.target.closest(".roster-item");
  if (!btn) return;
  const id = btn.dataset.id;
  const student = roster.find(s => s.id === id);
  if (!student) return;
  clearMsg();
  setSelectedStudent(student);
  renderRoster(currentRosterView());
});

rosterSearch.addEventListener("input", () => {
  renderRoster(currentRosterView());
});

function currentRosterView(){
  const q = rosterSearch.value.trim().toLowerCase();
  if (!q) return roster;
  return roster.filter(s =>
    String(s.id).toLowerCase().includes(q) || String(s.name).toLowerCase().includes(q)
  );
}

function resetSelectionAfterSave(){
  setSelectedStudent(null);
  rosterSearch.value = "";
  renderRoster(roster);
}

// -----------------------------------------------------------------------
// ปุ่มบันทึกสถานะ (พร้อมแอนิเมชันปั๊มตรา + กันเช็คซ้ำแบบเงียบ ๆ + อัปเดต weekly_stats)
// -----------------------------------------------------------------------
const inkStamp = document.getElementById("inkStamp");
const inkStampMark = document.getElementById("inkStampMark");
const colorMap = { "มาตรง":"--stamp-green", "มาสาย":"--stamp-red", "ขาด":"--stamp-slate" };

function playStamp(status, colorVar){
  inkStampMark.textContent = status;
  inkStampMark.style.color = `var(${colorVar})`;
  inkStamp.classList.remove("play");
  void inkStamp.offsetWidth; // reflow เพื่อ restart animation ได้ทุกครั้ง
  inkStamp.classList.add("play");
}

stampButtons.forEach(btn => {
  btn.addEventListener("click", async () => {
    if (!selectedStudent) return;
    const status = btn.dataset.status;
    clearMsg();

    const docId = `${selectedStudent.id}_${getDateKey()}`;
    const weekKey = getWeekKey();
    const statDocId = `${selectedStudent.id}_${weekKey}`;

    try {
      btn.disabled = true;

      const existingSnap = await getDoc(doc(db, "logs", docId));
      let oldStatus = null;

      if (existingSnap.exists()){
        oldStatus = existingSnap.data().status;
        if (oldStatus === status){
          formMsg.textContent = `บันทึกไว้แล้วว่า "${status}" สำหรับวันนี้`;
          resetSelectionAfterSave();
          return;
        }
        const confirmChange = window.confirm(
          `${selectedStudent.name} เช็คชื่อวันนี้ไปแล้วว่า "${oldStatus}"\nต้องการเปลี่ยนเป็น "${status}" หรือไม่?`
        );
        if (!confirmChange) return;
      }

      // --- 1. บันทึกประวัติลง Collection: logs ---
      await setDoc(doc(db, "logs", docId), {
        student_id: String(selectedStudent.id), // บังคับให้บันทึกเป็น String เสมอ
        status: status,
        timestamp: serverTimestamp()
      });

      // --- 2. อัปเดตสถิติลง Collection: weekly_stats ---
      const fieldMap = { "มาตรง": "present_count", "มาสาย": "late_count", "ขาด": "absent_count" };
      let statsUpdate = { student_id: String(selectedStudent.id) }; // บังคับให้บันทึกเป็น String เสมอ

      if (oldStatus) {
        // กรณีเปลี่ยนสถานะ
        statsUpdate[fieldMap[oldStatus]] = increment(-1);
        statsUpdate[fieldMap[status]] = increment(1);
      } else {
        // กรณีเช็คชื่อครั้งแรกของวัน
        statsUpdate[fieldMap[status]] = increment(1);
      }

      await setDoc(doc(db, "weekly_stats", statDocId), statsUpdate, { merge: true });

      playStamp(status, colorMap[status]);
      formMsg.textContent = `บันทึก "${status}" ให้ ${selectedStudent.name} แล้ว`;
      formMsg.classList.add("ok");
      resetSelectionAfterSave();
      loadStats(); // อัปเดตสถิติสะสมทันทีหลังบันทึก
    } catch (err) {
      console.error(err);
      formMsg.textContent = "บันทึกไม่สำเร็จ กรุณาตรวจสอบการเชื่อมต่อ Firebase";
    } finally {
      btn.disabled = !selectedStudent;
    }
  });
});

// -----------------------------------------------------------------------
// ฟีดประวัติแบบเรียลไทม์ (เฉพาะของวันนี้ ล่าสุด 8 รายการ)
// -----------------------------------------------------------------------
const logList = document.getElementById("logList");
const statusClassMap = { "มาตรง":"present", "มาสาย":"late", "ขาด":"absent" };

const recentLogsQuery = query(
  collection(db, "logs"),
  where("timestamp", ">=", Timestamp.fromDate(startOfToday())),
  orderBy("timestamp", "desc"),
  limit(8)
);

onSnapshot(recentLogsQuery, async (snapshot) => {
  if (snapshot.empty){
    logList.innerHTML = `<div class="feed-empty">ยังไม่มีการเช็คชื่อวันนี้</div>`;
    return;
  }

  const rows = await Promise.all(snapshot.docs.map(async (docSnap) => {
    const data = docSnap.data();
    const name = await fetchStudentName(data.student_id) || "ไม่พบชื่อ";
    const time = data.timestamp
      ? data.timestamp.toDate().toLocaleTimeString("th-TH", { hour12:false })
      : "…";
    const statusClass = statusClassMap[data.status] || "absent";

    // ทุกค่าที่มาจากผู้ใช้หรือฐานข้อมูลต้อง escape ก่อนแทรกลง innerHTML เสมอ
    return `
      <div class="log-row">
        <span class="log-id">${escapeHtml(data.student_id)}</span>
        <span class="log-name">${escapeHtml(name)}</span>
        <span class="log-status ${statusClass}">${escapeHtml(data.status)}</span>
        <span class="log-time">${escapeHtml(time)}</span>
      </div>
    `;
  }));

  logList.innerHTML = rows.join("");
}, (err) => {
  console.error("real-time listener error:", err);
  logList.innerHTML = `<div class="feed-empty">เชื่อมต่อเรียลไทม์ไม่สำเร็จ ตรวจสอบ firebaseConfig</div>`;
});

// -----------------------------------------------------------------------
// สถิติการเช็คชื่อสะสม (ดึงจาก weekly_stats โดยตรง)
// -----------------------------------------------------------------------
const statsBody = document.getElementById("statsBody");
const statsSearch = document.getElementById("statsSearch");
const statsSummary = document.getElementById("statsSummary");
let statsData = []; // [{ id, name, present, late, absent, total, rate }]

async function loadStats(){
  statsBody.innerHTML = `<tr><td colspan="6" class="stats-empty">กำลังโหลดสถิติ…</td></tr>`;
  try {
    // ดึงข้อมูลจาก Collection: weekly_stats แทน logs
    const snap = await getDocs(collection(db, "weekly_stats"));
    const counts = new Map(); // student_id -> { present, late, absent }

    snap.docs.forEach(d => {
      const data = d.data();
      const id = String(data.student_id); // บังคับให้เป็นข้อความ
      if (!id || id === "undefined") return;
      if (!counts.has(id)) counts.set(id, { present:0, late:0, absent:0 });
      
      const c = counts.get(id);
      // นำตัวเลขของแต่ละสัปดาห์มาบวกสะสมรวมกันให้เป็นสถิติทั้งเทอม
      c.present += (data.present_count || 0);
      c.late += (data.late_count || 0);
      c.absent += (data.absent_count || 0);
    });

    // เริ่มจากทุกคนในรายชื่อ roster (รวมคนที่ยังไม่มีสถิติ = 0 ทุกช่อง)
    const rows = roster.map(s => buildStatsRow(String(s.id), s.name, counts.get(String(s.id))));

    // เผื่อมี student_id ในสถิติที่ไม่อยู่ใน roster แล้ว
    counts.forEach((c, id) => {
      if (!roster.find(s => String(s.id) === id)){
        rows.push(buildStatsRow(id, studentNameCache.get(id) || "(ไม่พบชื่อในรายชื่อ)", c));
      }
    });

    statsData = rows;
    renderStats(currentStatsView());
  } catch (err) {
    console.error("โหลดสถิติไม่สำเร็จ:", err);
    statsBody.innerHTML = `<tr><td colspan="6" class="stats-empty">โหลดสถิติไม่สำเร็จ ตรวจสอบการเชื่อมต่อ Firebase</td></tr>`;
  }
}

function buildStatsRow(id, name, c){
  const counts = c || { present:0, late:0, absent:0 };
  const total = counts.present + counts.late + counts.absent;
  const rate = total ? Math.round(((counts.present + counts.late) / total) * 100) : null;
  return { id, name, ...counts, total, rate };
}

function currentStatsView(){
  const q = statsSearch.value.trim().toLowerCase();
  let list = statsData;
  if (q){
    list = list.filter(s =>
      String(s.id).toLowerCase().includes(q) || String(s.name).toLowerCase().includes(q)
    );
  }
  // เรียงให้คนที่ขาดเยอะสุดขึ้นก่อน โดยใช้ String(id) เสมอเพื่อป้องกัน TypeError
  return [...list].sort((a, b) => b.absent - a.absent || String(a.id).localeCompare(String(b.id), "th"));
}

function renderStats(list){
  if (!list.length){
    statsBody.innerHTML = `<tr><td colspan="6" class="stats-empty">ไม่พบข้อมูลนักศึกษา</td></tr>`;
    statsSummary.textContent = "";
    return;
  }

  statsBody.innerHTML = list.map(s => `
    <tr>
      <td class="st-id">${escapeHtml(s.id)}</td>
      <td class="st-name">${escapeHtml(s.name)}</td>
      <td class="st-num present">${s.present}</td>
      <td class="st-num late">${s.late}</td>
      <td class="st-num absent">${s.absent}</td>
      <td class="st-rate">${s.rate === null ? "—" : s.rate + "%"}</td>
    </tr>
  `).join("");

  statsSummary.textContent = `นักศึกษาทั้งหมด ${list.length} คน · เรียงตามจำนวนขาดมากไปน้อย`;
}

statsSearch.addEventListener("input", () => renderStats(currentStatsView()));

// -----------------------------------------------------------------------
// เริ่มโหลดข้อมูล: โหลด roster ก่อน แล้วค่อยคำนวณสถิติ (ต้องใช้ชื่อจาก roster)
// -----------------------------------------------------------------------
loadRoster().then(loadStats);