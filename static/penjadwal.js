/* ==========================================================================
   penjadwal.js — SATU mesin animasi untuk semua kanvas (Fase 3, rekomendasi R3).
   Analogi: satu sakelar lampu panggung. Lampu sebuah panggung hanya menyala bila panggung itu
   sedang DITONTON. Penonton pindah ke tab lain atau menggulir menjauh → lampunya padam.

   - IntersectionObserver : kanvas di luar layar (tergulir, mode tersembunyi, display:none) = tidak digambar.
   - Page Visibility API  : tab tidak aktif / jendela diminimalkan = SEMUA gambar berhenti.
   - Satu requestAnimationFrame untuk semua kanvas, dan rAF itu MATI TOTAL bila tidak ada
     kanvas yang perlu digambar (bukan sekadar "melewati" bingkai).
   Dipakai radar.js dan peta.js lewat: Penjadwal.daftar(nama, { elemen, gambar, boleh }).
   ========================================================================== */
"use strict";

const Penjadwal = (() => {
  const tugas = new Map();                  // nama -> { terlihat, gambar(t, dtMs), boleh() }
  let idRaf = 0, terakhir = 0;
  const statistik = { bingkai: 0 };         // untuk uji & pengukuran (lihat README)

  const siap = (x) => x.terlihat && x.boleh();

  function bingkai(t) {
    const dt = terakhir ? Math.min(t - terakhir, 50) : 16;   // lompatan setelah jeda tidak membuat animasi melompat
    terakhir = t;
    let ada = false;
    for (const x of tugas.values()) {
      if (!siap(x)) continue;
      x.gambar(t, dt);
      ada = true;
    }
    statistik.bingkai++;
    if (ada && !document.hidden) idRaf = requestAnimationFrame(bingkai);
    else { idRaf = 0; terakhir = 0; }       // tidak ada yang ditonton: mesin dimatikan
  }

  /** Nyalakan mesin bila ada kanvas yang siap dan tab sedang terlihat. Aman dipanggil berkali-kali. */
  function bangun() {
    if (idRaf || document.hidden) return;
    for (const x of tugas.values()) {
      if (siap(x)) { idRaf = requestAnimationFrame(bingkai); return; }
    }
  }

  function henti() { cancelAnimationFrame(idRaf); idRaf = 0; terakhir = 0; }

  document.addEventListener("visibilitychange", () => (document.hidden ? henti() : bangun()));

  return {
    /** Daftarkan satu kanvas. `boleh` = syarat tambahan milik modul (mis. radar dijeda, peta di mode mikro). */
    daftar(nama, { elemen, gambar, boleh = () => true }) {
      const x = { terlihat: false, gambar, boleh };
      tugas.set(nama, x);
      new IntersectionObserver(([e]) => {
        x.terlihat = e.isIntersecting;
        if (x.terlihat) bangun();             // kembali terlihat → nyala; tidak terlihat → padam sendiri di bingkai berikutnya
      }).observe(elemen);
    },
    bangun,
    berjalan: () => idRaf !== 0,
    statistik,
  };
})();
