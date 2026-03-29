(function () {
  "use strict";

  var LISTINGS_URL = "assets/data/ornek-ilanlar.json";
  var SITE_URL = "assets/data/site.json";
  var SOZLER_URL = "assets/data/sozler.json";

  var SOZLER_YEDEK = [
    "Paylaştığın her eşya, bir çöp tenekesinden kurtarılan küçük bir dünyadır.",
    "Eşyana yeni bir dünya, birine sessiz bir destek ver.",
    "Vermek, sahip olmanın en güzel biçimidir.",
    "Kullanmadığın her şey, başkasının en çok ihtiyaç duyduğu şey olabilir.",
    "Sürdürülebilirlik küçük adımlarla başlar; bugün dolabından başla.",
    "Doğaya verdiğin en büyük hediye, tüketimi azaltmak ve paylaşmaktır.",
    "Birlikte daha temiz, daha eşit ve daha yeşil bir gelecek.",
    "Dünyayı değiştirmek istiyorsan, etrafındaki geri dönüşüm çemberine katıl.",
  ];

  function showToast(message) {
    var el = document.getElementById("toast");
    if (!el) return;
    el.textContent = message;
    el.classList.add("show");
    setTimeout(function () {
      el.classList.remove("show");
    }, 3200);
  }

  function readEmbeddedJson(id) {
    var el = document.getElementById(id);
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent.trim());
    } catch (e) {
      return null;
    }
  }

  function kategoriEtiket(k) {
    if (k === "kitap") return "Kitap";
    if (k === "kiyafet") return "Kıyafet";
    if (k === "gida") return "Gıda";
    return k || "—";
  }

  function renderListings(container, data) {
    if (!container || !data || !data.ilanlar || !data.ilanlar.length) {
      container.innerHTML =
        '<p class="ilan-hata">Şu an gösterilecek ilan yok, ancak yakında harika şeyler gelecek!</p>';
      return;
    }
    
    var benimKutu = {};
    try { benimKutu = JSON.parse(localStorage.getItem('reworld_benim_ilanlarim') || "{}"); } catch(e){}

    container.innerHTML = data.ilanlar
      .map(function (item) {
        var gorselYolu = item.gorsel || "";
        if (!gorselYolu) {
            if (item.kategori === 'kitap') gorselYolu = "assets/img/kategori-kitap.svg";
            else if (item.kategori === 'kiyafet') gorselYolu = "assets/img/kategori-kiyafet.svg";
            else if (item.kategori === 'gida') gorselYolu = "assets/img/kategori-gida.svg";
            else gorselYolu = "assets/img/logo-mark.png";
        }
        
        var dObj = new Date(item.tarih || new Date());
        var tarihFormatli = dObj.toLocaleDateString("tr-TR");
        
        var btnSilHtml = "";
        if (benimKutu[item.id]) {
           btnSilHtml = '<button class="btn-sil" onclick="silBenimIlanim(' + item.id + ', \'' + benimKutu[item.id] + '\')">🗑️ İlanımı Kaldır</button>';
        }

        return (
          '<article class="need-card" id="ilan-card-' + item.id + '" style="display: flex; flex-direction: column;">' +
            '<div class="need-visual">' +
              '<img src="' + gorselYolu + '" alt="' + escapeHtml(item.kategori) + '" loading="lazy" width="320" height="200" style="object-fit: cover; width: 100%;" />' +
            '</div>' +
            '<div class="need-body" style="flex: 1; display:flex; flex-direction:column;">' +
              '<span class="need-tag">Bağış · ' + kategoriEtiket(item.kategori) + '</span>' +
              '<h3>' + escapeHtml(item.baslik) + '</h3>' +
              '<p class="need-desc">' + escapeHtml(item.aciklama || "Harika bir eşya.") + '</p>' +
              '<p class="need-meta" style="margin-top:auto; padding-bottom: 5px;">Konum: ' + escapeHtml(item.sehir || "—") + ' • ' + tarihFormatli + '</p>' +
              btnSilHtml +
            '</div>' +
          '</article>'
        );
      })
      .join("");
  }

  function escapeHtml(s) {
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function loadListings() {
    var container = document.querySelector("[data-reworld-listings]");
    if (!container) return;

    var filterCategory = container.getAttribute("data-reworld-listings") || "";
    var done = function (data, usedFallback) {
      // Eğer sahte veri gelmişse ve sayfada kategori filtresi varsa manuel filtrele
      if (usedFallback && filterCategory && filterCategory !== "all") {
        data.ilanlar = data.ilanlar.filter(function(i){ return i.kategori === filterCategory; });
      }
      renderListings(container, data);
      var err = document.getElementById("ilan-hata");
      if (err) err.hidden = !usedFallback;
    };

    var origin = "";
    try { origin = window.location.origin || ""; } catch(e){}
    var flaskUrl = origin + "/api/ilanlar";
    if (filterCategory && filterCategory !== "all") {
       flaskUrl += "?kategori=" + filterCategory;
    }

    // Her durumda API'yi (gerçek db) dene
    fetch(flaskUrl, { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("db_error");
        return r.json();
      })
      .then(function (data) {
        done(data, false);
      })
      .catch(function () {
        // Hata olursa sahte veriye düş (Görsel tutarlılığı için)
        fetch(LISTINGS_URL, { cache: "no-store" })
          .then(function (r) { return r.json(); })
          .then(function (data) { done(data, true); })
          .catch(function () {
            var emb = readEmbeddedJson("reworld-ilan-embed");
            if (emb && emb.ilanlar) done(emb, true);
            else done({ ilanlar: [] }, true);
          });
      });
  }

  function gunlukSozIndeksi(uzunluk) {
    var d = new Date();
    var damga =
      d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate();
    return damga % uzunluk;
  }

  function loadDailyQuote() {
    var span = document.querySelector("[data-reworld-soz]");
    if (!span) return;

    function uygula(liste) {
      if (!liste || !liste.length) return;
      var i = gunlukSozIndeksi(liste.length);
      span.textContent = liste[i];
    }

    fetch(SOZLER_URL, { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("soz");
        return r.json();
      })
      .then(function (data) {
        if (!Array.isArray(data) || !data.length) throw new Error("soz");
        uygula(data);
      })
      .catch(function () {
        var emb = readEmbeddedJson("reworld-sozler-embed");
        if (Array.isArray(emb) && emb.length) {
          uygula(emb);
        } else {
          uygula(SOZLER_YEDEK);
        }
      });
  }

  function loadSiteJsonOptional() {
    var el = document.querySelector("[data-site-policy]");
    if (!el) return;

    fetch(SITE_URL, { cache: "no-store" })
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .then(function (data) {
        if (data && data.politika) {
          el.textContent = data.politika;
        }
      })
      .catch(function () {});
  }

  function submitBagisForm(event) {
    if (event) event.preventDefault();
    var kategori = document.getElementById("kategori");
    var baslik = document.getElementById("baslik");
    var sehir = document.getElementById("sehir");
    var iletisim = document.getElementById("iletisim");
    var gorsel = document.getElementById("gorsel");

    if (!kategori || !baslik || !sehir) return;

    if (!kategori.value || !baslik.value.trim() || !sehir.value.trim()) {
      showToast("Lütfen kategori, başlık ve şehir alanlarını doldurun.");
      return;
    }
    if (iletisim && !iletisim.value.trim()) {
      showToast("İletişim alanını doldurun.");
      return;
    }

    var payloadFd = new FormData();
    payloadFd.append("kategori", kategori.value);
    payloadFd.append("baslik", baslik.value.trim());
    payloadFd.append("aciklama", document.getElementById("aciklama") ? document.getElementById("aciklama").value.trim() : "");
    payloadFd.append("sehir", sehir.value.trim());
    payloadFd.append("iletisim", iletisim ? iletisim.value.trim() : "-");
    if (gorsel && gorsel.files && gorsel.files[0]) {
      payloadFd.append("gorsel", gorsel.files[0]);
    }

    var apiBase =
      typeof window.REWORLD_API === "string" ? window.REWORLD_API : "";
    var origin = "";
    try {
      origin = window.location.origin || "";
    } catch (e) {}

    function postApi(url) {
      return fetch(url, {
        method: "POST",
        body: payloadFd,
      })
        .then(function (r) {
          return r.json().then(function (data) {
            return { ok: r.ok, data: data };
          });
        })
        .then(function (res) {
          if (res.ok) {
            showToast(res.data.mesaj || "İlanınız yayınlandı.");
            if (res.data.id && res.data.silme_kodu) {
               var benimKutu = {};
               try { benimKutu = JSON.parse(localStorage.getItem('reworld_benim_ilanlarim') || "{}"); } catch(e){}
               benimKutu[res.data.id] = res.data.silme_kodu;
               localStorage.setItem('reworld_benim_ilanlarim', JSON.stringify(benimKutu));
            }
            document.getElementById("bagis-form").reset();
          } else {
            showToast(res.data.hata || "Gönderim başarısız.");
          }
        });
    }

    if (window.REWORLD_USE_FLASK === true && origin.indexOf("http") === 0) {
      postApi(origin + "/api/ilan-olustur").catch(function () {
        showToast("Sunucu kapalı. İlan yüklenemedi!");
      });
      return;
    }

    if (apiBase) {
      var base = apiBase.replace(/\/$/, "");
      postApi(base + "/api/ilan-olustur").catch(function () {});
      return;
    }
    
    showToast("Flask kullanımdadır. Yerel sahte depolama iptal edildi.");
  }

  function kaydetYerel(payload) {
    try {
      var key = "reworld_yerel_ilanlar";
      var raw = localStorage.getItem(key);
      var list = raw ? JSON.parse(raw) : [];
      list.push({
        kategori: payload.kategori,
        baslik: payload.baslik,
        aciklama: payload.aciklama,
        sehir: payload.sehir,
        zaman: new Date().toISOString(),
      });
      localStorage.setItem(key, JSON.stringify(list));
      showToast(
        "Tarayıcıya kaydedildi (yerel). Sunucu yokken böyle saklanır."
      );
      document.getElementById("bagis-form").reset();
    } catch (e) {
      showToast("Kayıt yapılamadı. Sayfayı bir sunucu ile açtığınızdan emin olun.");
    }
  }

  function handleSihirliIlan() {
    var kategori = document.getElementById("kategori");
    var baslik = document.getElementById("baslik");
    var aciklama = document.getElementById("aciklama");
    var btn = document.getElementById("btn-sihir");

    if (!kategori || !baslik || !aciklama || !btn) return;

    var bVal = baslik.value.trim();
    var aVal = aciklama.value.trim();

    if (!bVal && !aVal) {
      showToast("Lütfen sihir kullanmadan önce eşyanın adını veya birkaç özelliğini yazın.");
      return;
    }

    var orjMetin = btn.innerHTML;
    btn.innerHTML = "✨ Düşünüyor...";
    btn.disabled = true;

    var origin = "";
    try {
      origin = window.location.origin || "";
    } catch (e) {}
    
    if (window.REWORLD_USE_FLASK === false || origin.indexOf("http") !== 0) {
       setTimeout(function() {
          baslik.value = "Mucizevi İyilik - " + (bVal || "Harika Eşya");
          aciklama.value = "Satmak veya çöpe atmak yerine buna ikinci bir şans vermek istedim. " + aVal + " Tertemiz ve yeni sahibini bekliyor.";
          btn.innerHTML = "✨ Yenilendi";
          showToast("Demo çalıştı! Gerçek yapay zeka (Gemini) için Flask gereklidir.");
          setTimeout(function(){ btn.disabled = false; btn.innerHTML = orjMetin; }, 3000);
       }, 1000);
       return;
    }

    fetch(origin + "/api/sihirli-ilan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kategori: kategori.value,
        baslik: bVal,
        aciklama: aVal
      }),
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      })
      .then(function (res) {
        if (res.ok && res.data.baslik && res.data.aciklama) {
          baslik.value = res.data.baslik;
          aciklama.value = res.data.aciklama;
          
          if (res.data.kategori && kategori) {
             var cleanKat = res.data.kategori.toLowerCase().replace(/[^a-z]/g, "");
             if (["kitap", "kiyafet", "gida"].indexOf(cleanKat) !== -1) {
                 kategori.value = cleanKat;
                 kategori.style.backgroundColor = "rgba(43,205,105,0.2)";
                 setTimeout(function(){ kategori.style.backgroundColor = ""; }, 2000);
             }
          }

          showToast("✨ İlanınız onaylandı. Yapay zeka kategoriyi de ayarladı!");
          btn.innerHTML = "✨ Hazır!";
        } else {
          showToast(res.data.hata || "Sihir gerçekleşmedi, sunucu yanıt vermiyor.");
          btn.innerHTML = "❌ Hata";
        }
        setTimeout(function(){ btn.disabled = false; btn.innerHTML = orjMetin; }, 3000);
      })
      .catch(function () {
        showToast("Sunucuya ulaşılamadı. Flask çalışmıyor olabilir.");
        btn.innerHTML = "❌ Hata";
        setTimeout(function(){ btn.disabled = false; btn.innerHTML = orjMetin; }, 3000);
      });
  }

  window.silBenimIlanim = function(ilan_id, silme_kodu) {
      if (!confirm("İlanınız hedefine ulaştı mı? Vitrinden tamamen kaldırılacaktır, onaylıyor musunuz?")) return;
      
      var origin = "";
      try { origin = window.location.origin || ""; } catch(e){}
      
      fetch(origin + "/api/ilan/" + ilan_id, {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ silme_kodu: silme_kodu })
      })
      .then(function(r) { return r.json().then(function(d){ return {ok: r.ok, data: d}; }); })
      .then(function(res) {
          if (res.ok) {
              showToast("🗑️ İlanınız platformdan tamamen kaldırıldı.");
              var card = document.getElementById("ilan-card-" + ilan_id);
              if (card) card.remove();
              
              var benimKutu = {};
              try { benimKutu = JSON.parse(localStorage.getItem('reworld_benim_ilanlarim') || "{}"); } catch(e){}
              if (benimKutu[ilan_id]) {
                  delete benimKutu[ilan_id];
                  localStorage.setItem('reworld_benim_ilanlarim', JSON.stringify(benimKutu));
              }
          } else {
              showToast(res.data.hata || "Silme işlemi başarısız.");
          }
      }).catch(function() { showToast("Sunucuya ulaşılamadı. Flask kapalı olabilir."); });
  };

  // Chatbot
  window.toggleChat = function() {
    var cb = document.getElementById("ai-chatbot");
    if (cb) {
      if (cb.classList.contains("collapsed")) {
        cb.classList.remove("collapsed");
        var input = document.getElementById("chat-input");
        if(input) input.focus();
      } else {
        cb.classList.add("collapsed");
      }
    }
  };

  window.handleChatKey = function(event) {
    if (event.key === "Enter") {
      sendChatMessage();
    }
  };

  window.sendChatMessage = function() {
    var input = document.getElementById("chat-input");
    var body = document.getElementById("chatbot-body");
    if (!input || !body) return;
    
    var msg = (input.value || "").trim();
    if (!msg) return;

    var userDiv = document.createElement("div");
    userDiv.className = "chat-message user-message";
    userDiv.textContent = msg;
    body.appendChild(userDiv);
    input.value = "";
    body.scrollTop = body.scrollHeight;

    var loadingDiv = document.createElement("div");
    loadingDiv.className = "chat-message ai-message";
    loadingDiv.textContent = "Asistan düşünüyor...";
    body.appendChild(loadingDiv);
    body.scrollTop = body.scrollHeight;

    var origin = "";
    try { origin = window.location.origin || ""; } catch(e){}

    fetch(origin + "/api/chatbot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mesaj: msg })
    })
    .then(function(r) { return r.json().then(function(d){ return {ok: r.ok, data: d}; }); })
    .then(function(res) {
       body.removeChild(loadingDiv);
       var aiDiv = document.createElement("div");
       aiDiv.className = "chat-message ai-message";
       if (res.data && res.data.cevap) {
          aiDiv.innerHTML = escapeHtml(res.data.cevap).replace(/\n/g, "<br>");
       } else {
          aiDiv.textContent = "Sistem hatası.";
       }
       body.appendChild(aiDiv);
       body.scrollTop = body.scrollHeight;
    })
    .catch(function() {
       body.removeChild(loadingDiv);
       var errDiv = document.createElement("div");
       errDiv.className = "chat-message ai-message";
       errDiv.textContent = "Bağlantı koptu. Flask sunucusunu kontrol edin.";
       body.appendChild(errDiv);
       body.scrollTop = body.scrollHeight;
    });
  };

  document.addEventListener("DOMContentLoaded", function () {
    loadDailyQuote();
    loadListings();
    loadSiteJsonOptional();

    var form = document.getElementById("bagis-form");
    if (form) {
      form.addEventListener("submit", submitBagisForm);
    }
    var btnSihir = document.getElementById("btn-sihir");
    if (btnSihir) {
      btnSihir.addEventListener("click", handleSihirliIlan);
    }
  });

  window.reworldShowToast = showToast;
})();
