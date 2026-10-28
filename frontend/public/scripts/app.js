const icons={grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',home:'<path d="m3 10 9-7 9 7v10H3z"/><path d="M9 20v-7h6v7"/>',book:'<path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1v15"/>',award:'<circle cx="12" cy="8" r="5"/><path d="m8 12-2 9 6-3 6 3-2-9"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',bell:'<path d="M5 17h14l-2-4V9a5 5 0 0 0-10 0v4zM10 21h4"/>',arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',logout:'<path d="M10 4H4v16h6m4-12 4 4-4 4m-6-4h12"/>',calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18"/>',check:'<path d="m5 12 4 4L19 6"/>',play:'<path d="m9 5 10 7-10 7z"/>',path:'<circle cx="5" cy="6" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 6h8a3 3 0 0 1 0 6H9a3 3 0 0 0 0 6h8"/>',target:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',users:'<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6"/>',user:'<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',chart:'<path d="M4 20V10m6 10V4m6 16v-7m4 7H2"/>',file:'<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7m-7 4h7"/>'};
const icon=n=>`<span class="ico"><svg viewBox="0 0 24 24" aria-hidden="true">${icons[n]||icons.book}</svg></span>`;
const brand=()=>`<a class="brand brand-logo" href="#dashboard" aria-label="ShimentoX dashboard"><img src="assets/images/ShimentoX-Light-Logo.webp" alt="ShimentoX" width="960" height="169"></a>`;
let state={completed:[],name:'',lesson:0};
let lessons=[];
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=()=>typeof courseProgress==='function'?courseProgress():0;
function toast(message){const t=document.getElementById('toast');t.textContent=message;t.classList.add('show');clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>t.classList.remove('show'),4000)}
let lesson, certificates;
function login(){return authPage();}
const PAGE_TITLES={course:'Course',history:'Learning history',assessments:'Assessments','course-preview':'Course preview',certificates:'My Certificates',courses:'My Learning',account:'My Profile'};
function pageTitle(page){
  if(page==='course')return currentCourseInfo.title||'Course';
  const item=portalNavigation().find(([href])=>href===page);
  return item?item[2]:PAGE_TITLES[page]||'Dashboard';
}
function pageContent(page){
  const pages={courses:candidateCourses,course:()=>lesson()+(currentCourseInfo.id&&!examActive()?courseExtras():''),certificates:()=>certificates(),account:accountPage,paths:pathsPage,skills:skillsPage,calendar:calendarPage,assessments:assessmentsPage,reports:()=>reportsPage(),'cert-records':()=>reportsPage('certificates'),history:historyPageView,'course-preview':coursePreviewPage};
  if(pages[page])return pages[page]();
  if(page.startsWith('admin-'))return adminPage(page);
  return ['admin','hr'].includes(currentUser.role)?adminDashboard():candidateDashboard();
}
function sidebarNavigation(active){
  return navigationGroups().map(item=>item.length===1?`<div class="nav-label nav-section">${esc(item[0])}</div>`:`<a href="#${item[0]}" class="${active===item[0]?'active':''}" ${active===item[0]?'aria-current="page"':''}>${icon(item[1])}${esc(item[2])}</a>`).join('');
}
function render(){if(!portalReady)return;const route=location.hash.slice(1);const page=resolvePage(route);const app=document.getElementById('app');
  if(page==='admin-setup'){document.title='Set up • ShimentoX';app.innerHTML=initialAdminPage();bindInitialAdmin();return;}
  if(page==='login'){document.title='Sign in • ShimentoX';app.innerHTML=login();bindAuthForm();return;}
  if(page==='password-setup'){document.title='Set your password • ShimentoX';app.innerHTML=passwordSetupPage();bindPasswordSetup();return;}
  const active=page==='course'?'courses':page==='history'?'courses':page==='course-preview'?'admin-courses':page,title=pageTitle(page);document.title=`${title} • ShimentoX`;
  app.innerHTML=`<div class="shell"><aside class="sidebar ${navigationGroups().length>8?'nav-long':''}">${brand()}<div class="brand-sub">LEARNING & DEVELOPMENT</div><div class="nav-label">YOUR WORKSPACE</div><nav class="nav" aria-label="Main navigation">${sidebarNavigation(active)}</nav><div class="side-bottom"><div class="help-box"><span style="font-size:20px;color:#7f9d8b">✧</span><h4 style="font-size:12px;margin:10px 0 0">A little help goes a long way.</h4><p>Find your way around your learning space.</p><a href="#dashboard">Explore the portal &nbsp; ↗</a></div></div></aside><main class="main"><header class="topbar"><div class="crumb">Workspace &nbsp; / &nbsp; <b>${esc(title)}</b></div><div class="top-actions"><div class="notification-wrap"><button class="icon-btn" id="notifications" aria-label="Notifications${notificationState.unread?`, ${notificationState.unread} unread`:''}" aria-expanded="${notificationState.open}">${icon('bell')}${notificationState.unread?`<span class="notification-count">${notificationState.unread>99?'99+':notificationState.unread}</span>`:''}</button>${notificationPanel()}</div><div class="profile"><span class="avatar">${esc(state.name.split(' ').map(x=>x[0]).slice(0,2).join(''))}</span><div class="profile-details"><strong>${esc(state.name)}</strong><small>${esc(ROLE_LABELS[currentUser.role]||'Employee')}</small><button class="profile-signout" id="logout-button" type="button">${icon('logout')} Sign out</button></div></div></div></header><div class="content">${outdatedServerNotice()}${pageContent(page)}<footer class="footer"><span>© ${new Date().getFullYear()} ShimentoX. Built for your growth.</span><span>Stay curious. Keep growing. &nbsp; ✧</span></footer></div></main></div>`;
  document.getElementById('notifications').onclick=()=>{notificationState.open=!notificationState.open;if(notificationState.open)refreshNotifications();render();};
  bindAccount();bindAdmin();const search=document.getElementById('search');if(search)search.oninput=()=>{document.querySelectorAll('[data-course-card]').forEach(card=>card.classList.toggle('hidden',!card.dataset.courseCard.includes(search.value.toLowerCase().trim())));}}

window.addEventListener('click',event=>{if(event.target.closest('[data-print-certificate]')&&location.hash==='#certificates'&&learning.certificates.length>0)window.print()});
window.addEventListener('hashchange',()=>{if(typeof endAttempts==='function')endAttempts('Attempt terminated: you navigated away from the exam.');notificationState.open=false;refreshOnNavigate();render();window.scrollTo(0,0)});
