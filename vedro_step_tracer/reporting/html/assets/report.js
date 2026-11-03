window.tracerCopyText = function (text, onDone) {
  var finish = onDone || function () {};
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(finish, finish);
    return;
  }
  var ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); } catch (e) { /* ignore */ }
  document.body.removeChild(ta);
  finish();
};

window.tracerCopyPath = function (btn) {
  var text = btn.getAttribute('data-copy') || '';
  tracerCopyText(text, function () {
    var original = btn.textContent;
    btn.textContent = '✓';
    btn.classList.add('tb-copied');
    setTimeout(function () {
      btn.textContent = original;
      btn.classList.remove('tb-copied');
    }, 1200);
  });
};

window.tracerCopyValue = function (btn) {
  var wrap = btn.closest('.v-item-value-wrap');
  var valueEl = wrap ? wrap.querySelector('.v-item-value, .block-body') : null;
  // Сокращённые хвосты скрыты через display:none и не попали бы в innerText,
  // поэтому на время копирования раскрываем их — в буфер уходит полное значение.
  var cuts = valueEl ? valueEl.querySelectorAll('.v-cut:not(.v-cut-open)') : [];
  for (var i = 0; i < cuts.length; i++) cuts[i].classList.add('v-cut-open');
  var text = valueEl ? valueEl.innerText.trim() : '';
  for (var j = 0; j < cuts.length; j++) cuts[j].classList.remove('v-cut-open');
  tracerCopyText(text, function () {
    btn.classList.add('copied');
    var original = btn.textContent;
    btn.textContent = '✓';
    setTimeout(function () {
      btn.textContent = original;
      btn.classList.remove('copied');
    }, 1000);
  });
};

// Раскрытие сокращённых значений: клик по `…` показывает скрытый хвост,
// повторный клик по раскрытому тексту с Alt сворачивает обратно.
document.addEventListener('click', function (event) {
  var dots = event.target.closest ? event.target.closest('.v-cut-dots') : null;
  if (dots) {
    event.preventDefault();
    event.stopPropagation();
    var cut = dots.parentNode;
    cut.classList.add('v-cut-open');
    return;
  }
  if (!event.altKey) return;
  var rest = event.target.closest ? event.target.closest('.v-cut-rest') : null;
  if (rest) {
    event.preventDefault();
    event.stopPropagation();
    rest.parentNode.classList.remove('v-cut-open');
  }
});

(function () {
  var links = Array.prototype.slice.call(document.querySelectorAll('.term-nav a'));
  if (!links.length || !('IntersectionObserver' in window)) return;
  var map = {};
  links.forEach(function (a) { map[a.getAttribute('href').slice(1)] = a; });
  var sections = document.querySelectorAll('.root-step[id]');
  var setActive = function (link) {
    links.forEach(function (a) { a.classList.remove('active'); });
    if (link) link.classList.add('active');
  };
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) setActive(map[entry.target.id]);
    });
  }, { rootMargin: '-10% 0px -75% 0px', threshold: 0 });
  sections.forEach(function (s) { observer.observe(s); });
})();

/* ── Sticky breadcrumbs: при скролле показываем цепочку заголовков ──── */
(function () {
  var bar = document.getElementById('sticky-crumbs');
  if (!bar) return;

  function getVisibleChain() {
    var scrollY = window.scrollY || window.pageYOffset;
    var barH = bar.offsetHeight || 0;
    var chain = [];

    /* Находим текущий root-step */
    var roots = document.querySelectorAll('.root-step[id]');
    var currentRoot = null;
    for (var i = roots.length - 1; i >= 0; i--) {
      if (roots[i].getBoundingClientRect().top <= barH + 10) {
        currentRoot = roots[i];
        break;
      }
    }
    if (!currentRoot || !currentRoot.hasAttribute('open')) return chain;

    /* Заголовок root step */
    var rootSummary = currentRoot.querySelector(':scope > summary');
    if (rootSummary && rootSummary.getBoundingClientRect().top < 0) {
      var rootHeader = rootSummary.querySelector('.root-header');
      chain.push({
        el: currentRoot,
        text: rootHeader ? rootHeader.innerText.trim() : rootSummary.innerText.trim(),
        depth: 0,
        color: getComputedStyle(currentRoot).getPropertyValue('--sc').trim() || '#6e7681'
      });
    }

    /* Вложенные details.node — ищем открытые, чей summary ушёл за верх */
    var nodes = currentRoot.querySelectorAll('details.node[open]');
    for (var j = 0; j < nodes.length; j++) {
      var nodeSummary = nodes[j].querySelector(':scope > summary');
      if (!nodeSummary) continue;
      var rect = nodeSummary.getBoundingClientRect();
      var parentRect = nodes[j].getBoundingClientRect();
      /* summary ушёл наверх, но сам блок ещё виден */
      if (rect.top < barH + 5 && parentRect.bottom > barH + 30) {
        chain.push({
          el: nodes[j],
          text: nodeSummary.innerText.trim(),
          depth: chain.length,
          color: getComputedStyle(nodes[j]).getPropertyValue('--nc').trim() || '#484f58'
        });
      }
    }
    return chain;
  }

  function render(chain) {
    if (!chain.length) {
      bar.innerHTML = '';
      bar.style.display = 'none';
      return;
    }
    bar.style.display = 'block';
    var html = '';
    for (var i = 0; i < chain.length; i++) {
      var c = chain[i];
      var indent = i * 12;
      html += '<div class="crumb crumb-depth-' + c.depth + '" data-idx="' + i + '" '
            + 'style="--crumb-color:' + c.color + ';padding-left:' + (16 + indent) + 'px">'
            + '<span class="crumb-name">' + c.text.substring(0, 120) + '</span>'
            + '</div>';
    }
    bar.innerHTML = html;

    /* Клик на крошку — скролл к заголовку элемента */
    var crumbs = bar.querySelectorAll('.crumb');
    for (var k = 0; k < crumbs.length; k++) {
      (function (idx) {
        crumbs[idx].addEventListener('click', function () {
          var target = chain[idx].el;
          var summary = target.querySelector(':scope > summary');
          if (summary) summary.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
      })(k);
    }
  }

  var ticking = false;
  function onScroll() {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(function () {
        render(getVisibleChain());
        ticking = false;
      });
    }
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll, { passive: true });
  /* Обновлять при toggle details */
  document.addEventListener('toggle', onScroll, true);
  onScroll();
})();

/* ── Копирование полного трейса для LLM ──────────────────────────────── */
/* Текст не собирается со страницы: значения переменных и возвраты лежат в
   свёрнутых <details>, а браузер не отдаёт текст скрытых элементов. Готовая
   plain-text выжимка встроена в страницу при генерации отчёта — см.
   HtmlTreeWriter._render_llm_payload. */
(function () {
  var btn = document.getElementById('copy-for-llm');
  if (!btn) return;

  function loadTrace() {
    var payload = document.getElementById('tracer-llm-payload');
    if (!payload) return '';
    try {
      return JSON.parse(payload.textContent);
    } catch (e) {
      return '';
    }
  }

  btn.addEventListener('click', function () {
    var text = loadTrace();
    var onDone = function () {
      btn.textContent = '✓ Скопировано';
      btn.classList.add('copied');
      setTimeout(function () {
        btn.textContent = '📋 Скопировать для LLM';
        btn.classList.remove('copied');
      }, 2000);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(onDone, onDone);
      return;
    }
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(ta);
    onDone();
  });
})();

/* ── Развернуть/свернуть все вызовы или все переменные одной кнопкой ─────── */
(function () {
  function wireToggle(btnId, selector, labelExpand, labelCollapse) {
    var btn = document.getElementById(btnId);
    if (!btn) return;
    btn.addEventListener('click', function () {
      var items = document.querySelectorAll(selector);
      var anyClosed = false;
      for (var i = 0; i < items.length; i++) {
        if (!items[i].open) { anyClosed = true; break; }
      }
      for (var j = 0; j < items.length; j++) { items[j].open = anyClosed; }
      btn.textContent = anyClosed ? labelCollapse : labelExpand;
    });
  }
  wireToggle('tracer-toggle-calls', 'details.node',
    '▾ Развернуть все вызовы', '▴ Свернуть все вызовы');
  wireToggle('tracer-toggle-vars', 'details.v-item',
    '▾ Развернуть все переменные', '▴ Свернуть все переменные');
})();

/* ── Поиск/фильтр по дереву: подсвечивает совпадения по имени вызова, ключу
   и значению переменной; с включённой галочкой "Скрывать несовпадающие"
   дополнительно скрывает всё, что не совпало само и не содержит совпадений
   во вложенных элементах — вложенность при этом сохраняется: путь до
   найденного элемента остаётся видимым и раскрывается автоматически ────── */
(function () {
  var input = document.getElementById('tracer-search-input');
  var filterCheckbox = document.getElementById('tracer-search-filter');
  if (!input) return;

  function ownText(el) {
    if (el.classList.contains('v-item')) {
      var summary = el.querySelector(':scope > summary');
      var value = el.querySelector(':scope > .v-item-value-wrap');
      return (summary ? summary.textContent : '') + ' ' + (value ? value.textContent : '');
    }
    var s = el.querySelector(':scope > summary');
    return s ? s.textContent : '';
  }

  function childUnits(el) {
    var container = el.querySelector(':scope > .node-body > .calls') ||
                     el.querySelector(':scope > .root-body > .calls');
    if (!container) return [];
    return Array.prototype.filter.call(container.children, function (c) {
      return c.matches('details.node, details.v-item');
    });
  }

  /* Возвращает true, если сам элемент или что-то в его поддереве совпало. */
  function applyFilter(el, query, filterOn) {
    var selfMatch = query !== '' && ownText(el).toLowerCase().indexOf(query) !== -1;
    var childMatch = false;
    var children = childUnits(el);
    for (var i = 0; i < children.length; i++) {
      if (applyFilter(children[i], query, filterOn)) childMatch = true;
    }
    var isVarItem = el.classList.contains('v-item');
    var isNode = el.classList.contains('node') || el.classList.contains('root-step');
    if (isVarItem || isNode) {
      el.classList.toggle('search-hit', selfMatch);
      // Подсвечиваем (слабее) и контейнеры, которые сами не совпали, но
      // остаются видимыми из-за совпадения во вложенных элементах —
      // так путь к найденному элементу виден на фоне остального дерева.
      el.classList.toggle('search-child-hit', !selfMatch && childMatch);
    }
    if (query !== '' && filterOn) {
      el.classList.toggle('search-hidden', !(selfMatch || childMatch));
      if (childMatch) el.open = true;
      else if (selfMatch && isVarItem) el.open = true;
    } else {
      el.classList.remove('search-hidden');
    }
    return selfMatch || childMatch;
  }

  function revealMatchingCuts(query) {
    var cuts = document.querySelectorAll('.v-cut');
    for (var i = 0; i < cuts.length; i++) {
      var rest = cuts[i].querySelector('.v-cut-rest');
      var hit = query !== '' && rest &&
        rest.textContent.toLowerCase().indexOf(query) !== -1;
      // Совпадение внутри скрытого хвоста иначе осталось бы невидимым.
      if (hit) cuts[i].classList.add('v-cut-open');
    }
  }

  function runSearch() {
    var query = input.value.trim().toLowerCase();
    var filterOn = !!(filterCheckbox && filterCheckbox.checked);
    var roots = document.querySelectorAll('.root-step[id]');
    for (var i = 0; i < roots.length; i++) {
      applyFilter(roots[i], query, filterOn);
    }
    revealMatchingCuts(query);
  }

  input.addEventListener('input', runSearch);
  if (filterCheckbox) filterCheckbox.addEventListener('change', runSearch);
})();
