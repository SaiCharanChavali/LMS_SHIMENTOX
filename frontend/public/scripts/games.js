// Revision games: Speed Quiz, Match Pairs and True or False Blitz.
// They replay the knowledge-check questions of lessons the employee has already passed (the server only
// releases those), so they reinforce learning without giving away answers to graded checks.
const GAMES={
  speed:{title:'Speed Quiz',emoji:'⚡',blurb:'Beat the clock. Build streaks for combo points.'},
  match:{title:'Match Pairs',emoji:'🧩',blurb:'Pair every question with its right answer.'},
  blitz:{title:'True or False Blitz',emoji:'🎯',blurb:'Rapid-fire: is the answer right or wrong?'}
};
const SPEED_SECONDS=15,SPEED_ROUNDS=10,MATCH_PAIRS=5,BLITZ_SECONDS=45,BLITZ_CARDS=16;
let gameState=null,gameTimer=null,gameDialog=null;

const gameShuffle=list=>{const a=[...list];for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a;};
const comboOf=streak=>streak>=6?3:streak>=3?2:1;

// Question sources: a lesson's inline quiz or linked assessment, plus the course's final assessment.
// Each one unlocks for play once the employee has passed it (the server enforces the same rule).
function gameCourseInfo(lesson){
  const assessments=currentCourseExtras?.assessments||[],lessons=currentCourseExtras?.courseLessons||[lesson];
  // Completing the course opens every game, including optional lesson checks that were skipped.
  const completed=Boolean(learning.run.completedAt),passedCheck=id=>completed||Boolean(assessments.find(a=>a.id===id)?.passed);
  const source=l=>l.quiz?.length?{passed:completed||Boolean(learning.run.lessons?.[l.id])}:l.assessmentId?{passed:passedCheck(l.assessmentId)}:null;
  const own=source(lesson),final=assessments.find(a=>a.kind==='post');
  const sources=[...lessons.map(source).filter(Boolean),...(final?[{passed:passedCheck(final.id)}]:[])];
  return {own,any:sources.length>0,anyPassed:sources.some(x=>x.passed)};
}
function gameBestKey(game,scope){return `sx-game-best:${currentUser?.id||'me'}:${currentCourseInfo?.id||''}:${scope}:${game}`;}
function gameBest(game,scope){try{return Number(localStorage.getItem(gameBestKey(game,scope)))||0;}catch{return 0;}}
function saveGameBest(game,scope,score){try{localStorage.setItem(gameBestKey(game,scope),String(score));}catch{}}

function gamesPanel(lesson){
  const {own,any,anyPassed}=gameCourseInfo(lesson);
  if(!any)return '';
  const ownOpen=Boolean(own?.passed),open=ownOpen||anyPassed,scopeKey=ownOpen?lesson.id:'all';
  const message=ownOpen?'Lock in what you learned with a quick game. Scores are just for fun and don’t affect your progress.'
    :open?(own?'This lesson’s questions unlock when you pass its knowledge check. Meanwhile, play with everything you’ve passed so far.':'This lesson has no questions of its own, so the games mix everything you’ve passed so far.')
    :own?'Pass this lesson’s knowledge check to unlock three revision games.':'Pass a knowledge check or the final assessment to unlock three revision games.';
  const tiles=Object.entries(GAMES).map(([key,g])=>{const best=open?gameBest(key,scopeKey):0;
    return `<button class="game-tile" data-game-start="${key}" data-lesson="${esc(lesson.id)}" data-own="${ownOpen}" ${open?'':'disabled'}><span class="game-tile-emoji" aria-hidden="true">${g.emoji}</span><b>${g.title}</b><small>${g.blurb}</small>${best?`<span class="game-tile-best">Best ${best}</span>`:''}</button>`;}).join('');
  const head=`<div class="games-head"><span class="games-icon" aria-hidden="true">🎮</span><div><h3>Play &amp; revise</h3><p>${message}</p></div>${open?'':'<span class="tag gray">🔒 Locked</span>'}</div>`;
  const scope=ownOpen?`<label class="games-scope">Questions from <select data-game-scope><option value="lesson">This lesson</option><option value="all">Everything I’ve passed</option></select></label>`:'';
  return `<section class="games-card ${open?'':'is-locked'}" aria-label="Revision games">${head}<div class="game-tiles">${tiles}</div>${scope}</section>`;
}

async function startGame(game,lessonId,scope){
  let data;
  try{data=await api(`me/games?courseId=${encodeURIComponent(currentCourseInfo.id)}`);}catch(error){return toast(error.message);}
  const lessons=scope==='all'?data.lessons:data.lessons.filter(l=>l.id===lessonId);
  const pool=lessons.flatMap(l=>l.questions.map(q=>({...q,lesson:l.title})));
  if(!pool.length)return toast('No game questions are available yet. Pass a knowledge check or the final assessment first.');
  gameState={game,scope:scope==='all'?'all':lessonId,pool,score:0,streak:0,bestStreak:0,correct:0,answered:0,missed:[]};
  openGameDialog();
  ({speed:speedSetup,match:matchSetup,blitz:blitzSetup})[game]();
}

function openGameDialog(){
  if(!gameDialog){
    gameDialog=document.createElement('dialog');
    gameDialog.className='game-dialog';
    gameDialog.setAttribute('aria-label','Revision game');
    gameDialog.addEventListener('close',()=>{stopGameTimer();gameState=null;});
    gameDialog.addEventListener('click',gameClick);
    gameDialog.addEventListener('keydown',gameKey);
    document.body.appendChild(gameDialog);
  }
  if(!gameDialog.open)gameDialog.showModal();
}
function stopGameTimer(){clearInterval(gameTimer);gameTimer=null;}
function gameFrame(body,{progress='',hud=true}={}){
  const g=GAMES[gameState.game],s=gameState;
  const stats=hud?`<div class="game-hud"><span><small>Score</small><b data-game-score>${s.score}</b></span><span class="${s.streak>=3?'is-hot':''}"><small>Streak</small><b>${s.streak>=3?'🔥 ':''}${s.streak}${comboOf(s.streak)>1?` <em>x${comboOf(s.streak)}</em>`:''}</b></span>${progress}</div>`:'';
  gameDialog.innerHTML=`<div class="game-shell game-${s.game}"><header class="game-top"><div class="game-name"><span aria-hidden="true">${g.emoji}</span>${g.title}</div><button class="game-close" data-game-act="close" aria-label="Close game">✕</button></header>${stats}<div class="game-stage">${body}</div></div>`;
  const focus=gameDialog.querySelector('[data-game-focus]')||gameDialog.querySelector('.game-stage button:not([disabled])');
  if(focus)focus.focus({preventScroll:true});
}
function gameTimerBar(fraction){return `<div class="game-timer" role="presentation"><span style="width:${Math.max(0,Math.min(1,fraction))*100}%"></span></div>`;}
function setTimerBar(fraction,seconds){
  const bar=gameDialog?.querySelector('.game-timer span'),label=gameDialog?.querySelector('[data-game-clock]');
  if(bar){bar.style.width=`${Math.max(0,fraction)*100}%`;bar.parentElement.classList.toggle('is-low',fraction<.3);}
  if(label)label.textContent=seconds;
}
function award(points){const s=gameState;s.streak++;s.bestStreak=Math.max(s.bestStreak,s.streak);s.correct++;s.answered++;const gained=Math.round(points*comboOf(s.streak));s.score+=gained;return gained;}
function miss(q){const s=gameState;s.streak=0;s.answered++;if(!s.missed.some(m=>m.prompt===q.prompt))s.missed.push(q);}

// ⚡ Speed Quiz: timed multiple choice; faster answers and streaks score more.
function speedSetup(){
  gameState.deck=gameShuffle(gameState.pool).slice(0,SPEED_ROUNDS).map(q=>({...q,choices:gameShuffle(q.options.map((text,i)=>({text,ok:i===q.answer})))}));
  gameState.round=0;speedRound();
}
function speedRound(){
  const s=gameState,q=s.deck[s.round];
  s.locked=false;s.deadline=Date.now()+SPEED_SECONDS*1000;
  const progress=`<span><small>Question</small><b>${s.round+1}<i>/${s.deck.length}</i></b></span><span><small>Time</small><b data-game-clock>${SPEED_SECONDS}</b></span>`;
  gameFrame(`${gameTimerBar(1)}<p class="game-lesson">${esc(q.lesson)}</p><h2 class="game-question">${esc(q.prompt)}</h2><div class="game-choices">${q.choices.map((c,i)=>`<button class="game-choice" data-game-choice="${i}"><kbd>${i+1}</kbd><span>${esc(c.text)}</span></button>`).join('')}</div><div class="game-feedback" role="status" aria-live="polite"></div>`,{progress});
  stopGameTimer();
  gameTimer=setInterval(()=>{const left=(s.deadline-Date.now())/1000;setTimerBar(left/SPEED_SECONDS,Math.max(0,Math.ceil(left)));if(left<=0)speedAnswer(-1);},100);
}
function speedAnswer(choice){
  const s=gameState;if(!s||s.locked)return;s.locked=true;stopGameTimer();
  const q=s.deck[s.round],right=q.choices[choice]?.ok===true,left=Math.max(0,Math.ceil((s.deadline-Date.now())/1000));
  gameDialog.querySelectorAll('.game-choice').forEach((b,i)=>{b.disabled=true;if(q.choices[i].ok)b.classList.add('is-right');else if(i===choice)b.classList.add('is-wrong');});
  let message;
  if(right){const gained=award(100+left*10);message=`<b class="good">+${gained} · Correct!</b>`;}
  else{miss(q);message=`<b class="bad">${choice<0?'⏰ Time’s up!':'Not quite.'}</b> The answer is <b>${esc(q.options[q.answer])}</b>.`;}
  const last=s.round+1>=s.deck.length;
  gameDialog.querySelector('.game-feedback').innerHTML=`<p>${message}${q.explanation?` <span>${esc(q.explanation)}</span>`:''}</p><button class="btn" data-game-act="next" data-game-focus>${last?'See results':'Next question'} ${icon('arrow')}</button>`;
  gameDialog.querySelector('[data-game-score]').textContent=s.score;
  gameDialog.querySelector('[data-game-act="next"]').focus({preventScroll:true});
}

// 🧩 Match Pairs: pick a question, then its answer. Fewer mistakes and a faster finish score more.
function matchSetup(){
  const seenPrompt=new Set(),seenAnswer=new Set(),deck=[];
  for(const q of gameShuffle(gameState.pool)){
    const answer=q.options[q.answer].trim().toLowerCase(),prompt=q.prompt.toLowerCase();
    if(seenPrompt.has(prompt)||seenAnswer.has(answer))continue;
    seenPrompt.add(prompt);seenAnswer.add(answer);deck.push(q);
    if(deck.length===MATCH_PAIRS)break;
  }
  if(deck.length<3){gameDialog.close();return toast('Not enough different questions for Match Pairs yet. Try “Everything I’ve passed”, or pass more lessons.');}
  Object.assign(gameState,{deck,answers:gameShuffle(deck.map((q,i)=>({text:q.options[q.answer],id:i}))),matched:new Set(),pick:null,mistakes:0,started:Date.now()});
  matchRender();
  gameTimer=setInterval(()=>{const clock=gameDialog?.querySelector('[data-game-clock]');if(clock)clock.textContent=`${Math.floor((Date.now()-gameState.started)/1000)}s`;},250);
}
function matchRender(){
  const s=gameState,card=(side,id,text,label)=>{const done=s.matched.has(id),picked=s.pick&&s.pick.side===side&&s.pick.id===id;
    return `<button class="match-card ${done?'is-matched':''} ${picked?'is-picked':''}" data-match-side="${side}" data-match-id="${id}" ${done?'disabled':''} aria-pressed="${picked}">${label?`<i>${label}</i>`:''}<span>${esc(text)}</span></button>`;};
  const progress=`<span><small>Pairs</small><b>${s.matched.size}<i>/${s.deck.length}</i></b></span><span><small>Mistakes</small><b>${s.mistakes}</b></span><span><small>Time</small><b data-game-clock>${Math.floor((Date.now()-s.started)/1000)}s</b></span>`;
  gameFrame(`<p class="game-hint">Tap a question, then tap its matching answer.</p><div class="match-board"><div class="match-col"><h4>Questions</h4>${s.deck.map((q,i)=>card('q',i,q.prompt,String.fromCharCode(65+i))).join('')}</div><div class="match-col"><h4>Answers</h4>${s.answers.map(a=>card('a',a.id,a.text,'')).join('')}</div></div><div class="game-feedback" role="status" aria-live="polite"></div>`,{progress});
}
function matchPick(side,id){
  const s=gameState;if(!s||s.busy||s.matched.has(id))return;
  if(!s.pick||s.pick.side===side){s.pick={side,id};return matchRender();}
  const qIndex=side==='q'?id:s.pick.id,aIndex=side==='a'?id:s.pick.id,q=s.deck[qIndex];
  s.pick=null;
  if(qIndex===aIndex){
    s.matched.add(qIndex);award(150);matchRender();
    gameDialog.querySelector('.game-feedback').innerHTML=`<p><b class="good">Matched!</b> ${q.explanation?esc(q.explanation):''}</p>`;
    if(s.matched.size===s.deck.length){stopGameTimer();s.score+=Math.max(0,120-Math.floor((Date.now()-s.started)/1000))*5;setTimeout(()=>{if(gameState===s)gameResults();},900);}
    return;
  }
  s.mistakes++;s.score=Math.max(0,s.score-40);miss(q);s.busy=true;
  gameDialog.querySelectorAll(`[data-match-side="q"][data-match-id="${qIndex}"],[data-match-side="a"][data-match-id="${aIndex}"]`).forEach(b=>b.classList.add('is-wrong'));
  setTimeout(()=>{if(gameState!==s)return;s.busy=false;matchRender();},650);
}

// 🎯 True or False Blitz: is the shown answer right? Streaks multiply points; the clock keeps running.
function blitzSetup(){
  const cards=gameState.pool.flatMap(q=>{const wrong=q.options.map((_,i)=>i).filter(i=>i!==q.answer);
    return [{q,claim:q.options[q.answer],truth:true},{q,claim:q.options[wrong[Math.floor(Math.random()*wrong.length)]],truth:false}];});
  Object.assign(gameState,{deck:gameShuffle(cards).slice(0,BLITZ_CARDS),round:0,deadline:Date.now()+BLITZ_SECONDS*1000});
  blitzRender();
  gameTimer=setInterval(()=>{const left=(gameState.deadline-Date.now())/1000;setTimerBar(left/BLITZ_SECONDS,Math.max(0,Math.ceil(left)));if(left<=0){stopGameTimer();gameResults();}},100);
}
function blitzRender(){
  const s=gameState,c=s.deck[s.round],left=Math.max(0,Math.ceil((s.deadline-Date.now())/1000));
  const progress=`<span><small>Card</small><b>${s.round+1}<i>/${s.deck.length}</i></b></span><span><small>Time</small><b data-game-clock>${left}</b></span>`;
  gameFrame(`${gameTimerBar((s.deadline-Date.now())/1000/BLITZ_SECONDS)}<div class="blitz-card"><p class="game-lesson">${esc(c.q.lesson)}</p><h2 class="game-question">${esc(c.q.prompt)}</h2><p class="blitz-claim"><small>Answer</small>${esc(c.claim)}</p></div><div class="blitz-buttons"><button class="blitz-btn is-false" data-blitz="false"><kbd>←</kbd> False</button><button class="blitz-btn is-true" data-blitz="true">True <kbd>→</kbd></button></div><div class="game-feedback" role="status" aria-live="polite"></div>`,{progress});
}
function blitzAnswer(value){
  const s=gameState;if(!s||s.locked||!s.deck)return;s.locked=true;
  const c=s.deck[s.round],right=value===c.truth;
  if(right)award(50);else miss(c.q);
  const card=gameDialog.querySelector('.blitz-card');card.classList.add(right?'is-right':'is-wrong');
  gameDialog.querySelectorAll('.blitz-btn').forEach(b=>b.disabled=true);
  gameDialog.querySelector('[data-game-score]').textContent=s.score;
  gameDialog.querySelector('.game-feedback').innerHTML=right?'<p><b class="good">Correct!</b></p>':`<p><b class="bad">Wrong.</b> Correct answer: <b>${esc(c.q.options[c.q.answer])}</b></p>`;
  setTimeout(()=>{if(gameState!==s||!gameTimer)return;s.locked=false;s.round++;
    if(s.round>=s.deck.length){stopGameTimer();s.score+=Math.max(0,Math.ceil((s.deadline-Date.now())/1000))*5;gameResults();}else blitzRender();},right?450:1300);
}

function gameResults(){
  const s=gameState;if(!s)return;stopGameTimer();
  const accuracy=s.answered?Math.round(s.correct/s.answered*100):0,best=gameBest(s.game,s.scope),record=s.score>best;
  if(record)saveGameBest(s.game,s.scope,s.score);
  const stars=accuracy>=90?3:accuracy>=60?2:accuracy>0?1:0;
  const review=s.missed.length?`<div class="game-review"><h3>Revise these</h3><ol>${s.missed.map(q=>`<li><b>${esc(q.prompt)}</b><span>✓ ${esc(q.options[q.answer])}</span>${q.explanation?`<small>${esc(q.explanation)}</small>`:''}</li>`).join('')}</ol></div>`
    :'<p class="game-perfect">Flawless — no mistakes! 🎉</p>';
  gameFrame(`<div class="game-results"><div class="game-stars" aria-label="${stars} of 3 stars">${[1,2,3].map(i=>`<span class="${i<=stars?'on':''}">★</span>`).join('')}</div><p class="game-final"><small>Final score</small><b>${s.score}</b></p>${record?'<p class="game-record">🏆 New personal best!</p>':best?`<p class="game-best">Personal best: ${best}</p>`:''}<div class="game-summary"><span><b>${accuracy}%</b><small>Accuracy</small></span><span><b>${s.correct}/${s.answered}</b><small>Correct</small></span><span><b>${s.bestStreak}</b><small>Best streak</small></span></div>${review}<div class="game-actions"><button class="btn" data-game-act="again" data-game-focus>Play again ${icon('refresh')}</button>${Object.keys(GAMES).filter(k=>k!==s.game).map(k=>`<button class="btn secondary" data-game-act="switch" data-game="${k}">${GAMES[k].emoji} ${GAMES[k].title}</button>`).join('')}<button class="btn secondary" data-game-act="close">Close</button></div></div>`,{hud:false});
}
function restartGame(game){
  const s=gameState;stopGameTimer();
  gameState={game,scope:s.scope,pool:s.pool,score:0,streak:0,bestStreak:0,correct:0,answered:0,missed:[]};
  ({speed:speedSetup,match:matchSetup,blitz:blitzSetup})[game]();
}

function gameClick(event){
  if(event.target===gameDialog)return gameDialog.close();
  const el=event.target.closest('button');if(!el||!gameState)return;
  const act=el.dataset.gameAct;
  if(act==='close')return gameDialog.close();
  if(act==='next'){gameState.round++;return gameState.round>=gameState.deck.length?gameResults():speedRound();}
  if(act==='again')return restartGame(gameState.game);
  if(act==='switch')return restartGame(el.dataset.game);
  if(el.dataset.gameChoice!==undefined)return speedAnswer(Number(el.dataset.gameChoice));
  if(el.dataset.matchSide)return matchPick(el.dataset.matchSide,Number(el.dataset.matchId));
  if(el.dataset.blitz)return blitzAnswer(el.dataset.blitz==='true');
}
function gameKey(event){
  const s=gameState;if(!s||event.altKey||event.ctrlKey||event.metaKey)return;
  if(s.game==='speed'&&!s.locked&&/^[1-9]$/.test(event.key)&&s.deck?.[s.round]?.choices[Number(event.key)-1]){event.preventDefault();speedAnswer(Number(event.key)-1);}
  else if(s.game==='blitz'&&s.deck&&!s.locked&&gameTimer){
    if(['ArrowLeft','f','F'].includes(event.key)){event.preventDefault();blitzAnswer(false);}
    else if(['ArrowRight','t','T'].includes(event.key)){event.preventDefault();blitzAnswer(true);}
  }
}

document.addEventListener('click',event=>{
  const tile=event.target.closest('[data-game-start]');
  if(!tile||tile.disabled)return;
  const scope=tile.dataset.own==='true'?tile.closest('.games-card')?.querySelector('[data-game-scope]')?.value||'lesson':'all';
  startGame(tile.dataset.gameStart,tile.dataset.lesson,scope);
});
