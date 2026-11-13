const icons={filter:'<path d="M4 5h16l-6 8v5l-4 2v-7z"/>',download:'<path d="M12 4v11m-5-5 5 5 5-5M5 20h14"/>',refresh:'<path d="M20 11a8 8 0 1 0-2 6.3M20 5v6h-6"/>',eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',home:'<path d="m3 10 9-7 9 7v10H3z"/><path d="M9 20v-7h6v7"/>',book:'<path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1v15"/>',award:'<circle cx="12" cy="8" r="5"/><path d="m8 12-2 9 6-3 6 3-2-9"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',bell:'<path d="M5 17h14l-2-4V9a5 5 0 0 0-10 0v4zM10 21h4"/>',arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',logout:'<path d="M10 4H4v16h6m4-12 4 4-4 4m-6-4h12"/>',calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18"/>',check:'<path d="m5 12 4 4L19 6"/>',play:'<path d="m9 5 10 7-10 7z"/>',path:'<circle cx="5" cy="6" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 6h8a3 3 0 0 1 0 6H9a3 3 0 0 0 0 6h8"/>',target:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',users:'<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6"/>',user:'<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',chart:'<path d="M4 20V10m6 10V4m6 16v-7m4 7H2"/>',file:'<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7m-7 4h7"/>',moon:'<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'};
const icon=n=>`<span class="ico"><svg viewBox="0 0 24 24" aria-hidden="true">${icons[n]||icons.book}</svg></span>`;
const brand=()=>`<a class="brand brand-logo" href="#dashboard" aria-label="ShimentoX dashboard"><img src="assets/images/ShimentoX-Light-Logo.webp" alt="ShimentoX" width="960" height="169"></a>`;
let state={completed:[],name:'',lesson:0};
let lessons=[];
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=()=>typeof courseProgress==='function'?courseProgress():0;
function toast(message){const t=document.getElementById('toast');t.textContent=message;t.classList.add('show');clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>t.classList.remove('show'),4000)}
let lesson, certificates;
// Light or dark theme: the choice is kept in this browser only (a display preference, not account data).
// Dark styles are generated per stylesheet into styles/dark/ by frontend/tools/build_dark_theme.py.
const THEME_KEY='shimentox-theme';
let theme=(()=>{try{return localStorage.getItem(THEME_KEY)==='dark'?'dark':'light';}catch{return 'light';}})();
function applyTheme(){try{document.documentElement.dataset.theme=theme;document.querySelector('meta[name="theme-color"]')?.setAttribute('content',theme==='dark'?'#121619':'#fbc02d');}catch{/* No document (tests). */}}
function toggleTheme(){theme=theme==='dark'?'light':'dark';try{localStorage.setItem(THEME_KEY,theme);}catch{/* Private mode: the choice lasts for this page only. */}applyTheme();const button=document.getElementById('theme-toggle');if(button)button.outerHTML=themeButton();bindThemeButton();}
const themeButton=()=>`<button class="icon-btn theme-toggle" id="theme-toggle" type="button" aria-pressed="${theme==='dark'}" aria-label="${theme==='dark'?'Switch to light mode':'Switch to dark mode'}" title="${theme==='dark'?'Light mode':'Dark mode'}">${icon(theme==='dark'?'sun':'moon')}</button>`;
function bindThemeButton(){const button=document.getElementById('theme-toggle');if(button)button.onclick=toggleTheme;}
applyTheme();
// Printed pages (certificates, reports) always use the light theme.
window.addEventListener('beforeprint',()=>{try{document.documentElement.dataset.theme='light';}catch{}});
window.addEventListener('afterprint',applyTheme);
function login(){return authPage();}
const PAGE_TITLES={course:'Course',history:'Learning history',assessments:'Assessments','course-preview':'Course preview',certificates:'My Certificates',courses:'My Learning',catalog:'Courses',account:'My Profile'};
function pageTitle(page){
  if(page==='course')return currentCourseInfo.title||'Course';
  const item=portalNavigation().find(([href])=>href===page);
  return item?item[2]:PAGE_TITLES[page]||'Dashboard';
}
function pageContent(page){
  const pages={courses:myLearningPage,catalog:candidateCourses,course:()=>lesson()+(currentCourseInfo.id&&!examActive()?courseExtras():''),certificates:()=>certificates(),account:accountPage,calendar:calendarPage,assessments:assessmentsPage,compliance:compliancePage,onboarding:onboardingPage,reports:()=>reportsPage(),'cert-records':()=>reportsPage('certificates'),history:historyPageView,'learning-activity':learningActivityPage,'course-preview':coursePreviewPage};
  if(pages[page])return pages[page]();
  if(page.startsWith('admin-'))return adminPage(page);
  return ['admin','hr'].includes(currentUser.role)?adminDashboard():candidateDashboard();
}
function sidebarNavigation(active){
  return navigationGroups().map(item=>item.length===1?`<div class="nav-label nav-section">${esc(item[0])}</div>`:`<a href="#${item[0]}" class="${active===item[0]?'active':''}" ${active===item[0]?'aria-current="page"':''}>${icon(item[1])}${esc(item[2])}</a>`).join('');
}
// Entrance motion (polish.css) plays when the page changes, not when the same page re-renders after a click or data load.
let lastRenderedPage=null,enterTimer=null,countedStats=new Set();
const prefersMotion=()=>{try{return !window.matchMedia||!matchMedia('(prefers-reduced-motion: reduce)').matches;}catch{return true;}};
function markPageEnter(app,page){
  if(page===lastRenderedPage)return;
  lastRenderedPage=page;countedStats=new Set();
  try{app.setAttribute('data-enter','');clearTimeout(enterTimer);enterTimer=setTimeout(()=>app.removeAttribute('data-enter'),1200);}catch{/* Test sandbox. */}
}
// Headline numbers count up from zero the first time they appear after navigating to a page.
function countUpStats(){
  if(typeof requestAnimationFrame!=='function'||!prefersMotion())return;
  document.querySelectorAll('.stat strong,.mini-stat strong,.compliance-kpi strong').forEach((el,i)=>{
    const match=/^(\d{1,7})(%?)$/.exec(el.textContent.trim()),key=i+':'+el.textContent;
    if(!match||countedStats.has(key)||Number(match[1])===0)return;
    countedStats.add(key);
    const target=Number(match[1]),suffix=match[2],start=performance.now(),duration=Math.min(900,350+target*12);
    const step=now=>{const t=Math.min(1,(now-start)/duration),eased=1-Math.pow(1-t,3);el.textContent=Math.round(target*eased)+suffix;if(t<1)requestAnimationFrame(step);};
    requestAnimationFrame(step);
  });
}
function render(){if(!portalReady)return;const route=location.hash.slice(1);const page=resolvePage(route);const app=document.getElementById('app');markPageEnter(app,page);
  if(page==='admin-setup'){document.title='Set up • ShimentoX';app.innerHTML=initialAdminPage();bindInitialAdmin();return;}
  if(page==='login'){document.title='Sign in • ShimentoX';app.innerHTML=login();bindAuthForm();return;}
  if(page==='password-setup'){document.title='Set your password • ShimentoX';app.innerHTML=passwordSetupPage();bindPasswordSetup();return;}
  const active=page==='course'?'courses':page==='history'?'courses':page==='course-preview'?'admin-courses':page,title=pageTitle(page);document.title=`${title} • ShimentoX`;
  app.innerHTML=`<div class="shell"><aside class="sidebar ${navigationGroups().length>8?'nav-long':''}">${brand()}<div class="brand-sub">LEARNING & DEVELOPMENT</div><div class="nav-label">YOUR WORKSPACE</div><nav class="nav" aria-label="Main navigation">${sidebarNavigation(active)}</nav><div class="side-bottom"><div class="help-box"><span style="font-size:20px;color:#7f9d8b">✧</span><h4 style="font-size:12px;margin:10px 0 0">A little help goes a long way.</h4><p>Find your way around your learning space.</p><a href="#dashboard">Explore the portal &nbsp; ↗</a></div></div></aside><main class="main"><header class="topbar"><div class="crumb">Workspace &nbsp; / &nbsp; <b>${esc(title)}</b></div><div class="top-actions">${themeButton()}<div class="notification-wrap"><button class="icon-btn" id="notifications" aria-label="Notifications${notificationState.unread?`, ${notificationState.unread} unread`:''}" aria-expanded="${notificationState.open}">${icon('bell')}${notificationState.unread?`<span class="notification-count">${notificationState.unread>99?'99+':notificationState.unread}</span>`:''}</button>${notificationPanel()}</div><div class="profile"><span class="avatar">${esc(state.name.split(' ').map(x=>x[0]).slice(0,2).join(''))}</span><div class="profile-details"><strong>${esc(state.name)}</strong><small>${esc(ROLE_LABELS[currentUser.role]||'Employee')}</small><button class="profile-signout" id="logout-button" type="button">${icon('logout')} Sign out</button></div></div></div></header><div class="content">${outdatedServerNotice()}${pageContent(page)}<footer class="footer"><span>© ${new Date().getFullYear()} ShimentoX. Built for your growth.</span><span>Stay curious. Keep growing. &nbsp; ✧</span></footer></div></main></div>`;
  document.getElementById('notifications').onclick=()=>{notificationState.open=!notificationState.open;if(notificationState.open)refreshNotifications();render();};
  bindThemeButton();bindAccount();bindAdmin();const search=document.getElementById('search');if(search){
    // Search narrows the cards the category and status filters show; category sections with no match are hidden.
    const apply=()=>{const query=search.value.toLowerCase().trim();if(search.hasAttribute('data-remember-search'))courseSearch=search.value;
      document.querySelectorAll('[data-course-card]').forEach(card=>card.classList.toggle('hidden',!card.dataset.courseCard.includes(query)));
      const sections=[...document.querySelectorAll('[data-course-section]')];sections.forEach(s=>s.classList.toggle('hidden',!s.querySelector('[data-course-card]:not(.hidden)')));
      document.getElementById('search-empty')?.classList.toggle('hidden',!sections.length||sections.some(s=>!s.classList.contains('hidden')));};
    search.oninput=apply;if(search.value)apply();}
  countUpStats();}

window.addEventListener('click',event=>{if(event.target.closest('[data-print-certificate]')&&location.hash==='#certificates'&&learning.certificates.length>0)window.print()});
window.addEventListener('hashchange',()=>{if(typeof endAttempts==='function')endAttempts('Attempt terminated: you navigated away from the exam.');notificationState.open=false;refreshOnNavigate();render();window.scrollTo(0,0)});
