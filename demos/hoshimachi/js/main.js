window.onload = function() {
  

  const canvas = document.getElementById('stars');
  const ctx = canvas.getContext('2d');

  let stars = [];
  let shootingStars = [];
  let width, height;

  let mouseX = 0;
  let mouseY = 0;
  let cursorX = 0;
  let cursorY = 0;

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }

  function createStar() {
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      size: Math.random() * 1.5,
      opacity: Math.random(),
      speed: Math.random() * 0.02
    };
  }

  function createShootingStar() {
    return {
      x: Math.random() * width,
      y: 0,
      length: Math.random() * 120 + 80,
      speed: Math.random() * 8 + 6,
      angle: Math.PI / 4 + Math.random() * 0.2,
      opacity: 1
    };
  }

  function init() {
    resize();
    for (let i = 0; i < 200; i++) {
      stars.push(createStar());
    }
  }

  function draw() {
    ctx.clearRect(0, 0, width, height);

    //  ดาวพื้นหลัง
    stars.forEach(star => {
      star.opacity += star.speed;

      if (star.opacity > 1 || star.opacity < 0.2) {
        star.speed *= -1;
      }

      ctx.beginPath();
      ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,255,255,${star.opacity})`;
      ctx.fill();
    });

    //  สร้างดาวหาง
    if (Math.random() < 0.005 && shootingStars.length < 1) {
      shootingStars.push(createShootingStar());
    }

    //  วาดดาวหาง
    shootingStars.forEach((shootingStar, index) => {

      const xEnd = shootingStar.x + Math.cos(shootingStar.angle) * shootingStar.length;
      const yEnd = shootingStar.y + Math.sin(shootingStar.angle) * shootingStar.length;

      const gradient = ctx.createLinearGradient(
        shootingStar.x,
        shootingStar.y,
        xEnd,
        yEnd
      );

      gradient.addColorStop(0, `rgba(255,255,255,${shootingStar.opacity})`);
      gradient.addColorStop(1, `rgba(255,255,255,0)`);

      ctx.strokeStyle = gradient;

      ctx.beginPath();
      ctx.moveTo(shootingStar.x, shootingStar.y);
      ctx.lineTo(xEnd, yEnd);
      ctx.lineWidth = 1.5;
      ctx.stroke();

      shootingStar.x += Math.cos(shootingStar.angle) * shootingStar.speed;
      shootingStar.y += Math.sin(shootingStar.angle) * shootingStar.speed;

      shootingStar.opacity -= 0.02;

      if (shootingStar.opacity <= 0) {
        shootingStars.splice(index, 1);
      }
    });

    requestAnimationFrame(draw);
  };

  window.addEventListener("resize", resize);

  window.addEventListener("mousemove", (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
  });

  init();
  draw();

  // Discography
  const albums = [
    'Still Still Stellar','新星目録','AWAKE','Orbital Period',
    'ムーンライト','GHOST','NEXT COLOR PLANET','Bluerose / comet',
    'ビビデバ','駆けろ / 天球、彗星は夜を跨いで','放送室',
    'ソワレ','彗星','TEMPLATE','自分勝手Dazzling'
  ];

  const container = document.querySelector('.disco-scroll');
  const symbols = ['✦','✧','⋆','·','★','☆','◇'];

  albums.forEach((title, i) => {
    const sym = symbols[i % symbols.length];
    const hue = 220 + (i * 15) % 60;
    container.innerHTML += `
      <div class="disco-card">
        <div class="disco-card-img" style="background: hsl(${hue},30%,12%);">
          <span class="disco-card-star">${sym}</span>
          <span class="disco-card-num">${String(i+1).padStart(2, '0')} </span>
        </div>
        <div class="disco-card-title">${title}</div>
      </div>`;
  });

  // ลูกกลมตามเมาส์ 
    const dot = document.getElementById('cursor');
    const ring = document.getElementById('cursor-ring');
    let rx = 0, ry =0;

    window.addEventListener('mousemove', (e) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
      dot.style.left = mouseX + 'px';
      dot.style.top = mouseY + 'px';
    });
    function animRing() {
      rx += (mouseX - rx) * 0.12;
      ry += (mouseY - ry) * 0.12;
      ring.style.left = rx + 'px';
      ring.style.top = ry + 'px';
      requestAnimationFrame(animRing);
    }
    animRing();


  // Smooth scroll โดยไม่เปลี่ยน URL
  document.querySelectorAll('a[href^="#"]').forEach(link => {
      link.addEventListener('click', (e) => {
          e.preventDefault();
          const target = document.querySelector(link.getAttribute('href'));
          if (target) {
              target.scrollIntoView({ behavior: 'smooth' });
          }
      });
  });


};