// @ts-nocheck
// Imperative three.js engine for the metaverse. Ported from the standalone single-file version in ../standalone.
// It is intentionally framework-free: React only mounts the shadow root and calls startMetaverse().
import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { GammaCorrectionShader } from 'three/examples/jsm/shaders/GammaCorrectionShader.js';
import type { World } from './types';

export type SaveData = { wallet: number; life: number; owned: string[]; look: Record<string, string | null>; rev: number };
export type StartOptions = {
  extraWorlds?: Record<string, World>;
  onExit?: () => void;
  /** Asks the AI for a world about a typed topic. Reports progress (0-1) and a stage name while it works. */
  onBuild?: (topic: string, onProgress: (p: number, stage: string) => void) => Promise<World>;
  /** A second home for points and purchases, so they survive another address or cleared browser data. */
  store?: { load: () => Promise<SaveData | null>; save: (d: SaveData) => void };
};

export function startMetaverse(root: ShadowRoot, opts: StartOptions = {}): () => void {
const $=s=>root.querySelector(s);
const extra=opts.extraWorlds||{};
let dead=false,raf=0;const offs=[];
const on=(t,f)=>{window.addEventListener(t,f);offs.push(()=>window.removeEventListener(t,f))};
const noop=()=>{};
const K=h=>new THREE.Color(h).convertSRGBToLinear();
const rng=seed=>()=>{seed|=0;seed=seed+0x6D2B79F5|0;let t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296};

/* ---------------- lesson data: same shape the local model returns (zones of info + quiz) ---------------- */
const WORLDS={
java:{title:'Java',zones:[
 {name:'Objects',color:'#62e6ff',info:{title:'Classes and objects',body:'A class is a blueprint. An object is one thing built from it. Every Dog you create with new gets its own name and age.',terms:['class','object','new'],code:'Dog rex = new Dog("Rex", 3);'},quiz:{q:'Which keyword creates an object from a class?',options:['new','this','static','final'],answer:0,hint:'You write it right before the class name and the parentheses.'}},
 {name:'The JVM',color:'#ffb454',info:{title:'Write once, run anywhere',body:'javac turns your .java file into bytecode. The Java Virtual Machine runs that bytecode, so the same program runs on Windows, macOS and Linux.',terms:['javac','bytecode','JVM'],code:'javac Hello.java\njava Hello'},quiz:{q:'What does the JVM actually run?',options:['Bytecode','Source code','HTML','Only native machine code'],answer:0,hint:'javac produces it from your source file.'}},
 {name:'Inheritance',color:'#ff6fa8',info:{title:'Reuse with extends',body:'A subclass inherits fields and methods from its parent class and can override them. Use extends to say that a Cat is an Animal.',terms:['extends','override','super'],code:'class Cat extends Animal {\n  @Override void speak() { /* meow */ }\n}'},quiz:{q:'Which keyword makes one class inherit from another?',options:['extends','implements','inherits','super'],answer:0,hint:'implements is used for interfaces.'}},
 {name:'Collections',color:'#74ffb8',info:{title:'Lists and maps',body:'ArrayList is a resizable list. HashMap stores key and value pairs and finds a value by its key very quickly.',terms:['ArrayList','HashMap','generics'],code:'Map<String,Integer> ages = new HashMap<>();\nages.put("Asha", 14);'},quiz:{q:'Which collection stores key and value pairs?',options:['HashMap','ArrayList','Stack','Queue'],answer:0,hint:'Think of a dictionary.'}}
 ],finale:{title:'Summit reached',body:'You can now create objects, explain the JVM, extend classes and pick the right collection.'}},
photosynthesis:{title:'Photosynthesis',zones:[
 {name:'Sunlight',color:'#ffd05a',info:{title:'Light is the energy',body:'Leaves capture sunlight. That energy drives the reaction that builds sugar from simple ingredients.',terms:['light','energy','leaf']},quiz:{q:'What is the energy source for photosynthesis?',options:['Sunlight','Soil','Wind','Heat from the roots'],answer:0,hint:'It arrives from the sky every day.'}},
 {name:'Raw materials',color:'#62e6ff',info:{title:'Water and carbon dioxide',body:'Roots absorb water. Leaves take in carbon dioxide through tiny pores called stomata.',terms:['stomata','roots','CO₂']},quiz:{q:'Which gas do leaves take in?',options:['Carbon dioxide','Oxygen','Nitrogen','Hydrogen'],answer:0,hint:'It is the gas we breathe out.'}},
 {name:'Chlorophyll',color:'#74ffb8',info:{title:'The green pigment',body:'Chlorophyll absorbs red and blue light and reflects green. That is why leaves look green.',terms:['chlorophyll','pigment','chloroplast']},quiz:{q:'Why do leaves look green?',options:['Chlorophyll reflects green light','Water is green','Soil colours them','They absorb green light'],answer:0,hint:'The colour you see is the light that bounces back.'}},
 {name:'Products',color:'#ff6fa8',info:{title:'Glucose and oxygen',body:'The plant keeps the glucose as food. Oxygen is released into the air as a by-product.',terms:['glucose','oxygen','by-product'],code:'6CO₂ + 6H₂O + light → C₆H₁₂O₆ + 6O₂'},quiz:{q:'Which gas is released?',options:['Oxygen','Carbon dioxide','Nitrogen','Methane'],answer:0,hint:'Animals need it to breathe.'}}
 ],finale:{title:'Summit reached',body:'Light, water and carbon dioxide go in. Glucose and oxygen come out. Chlorophyll makes it happen.'}},
water:{title:'The water cycle',zones:[
 {name:'Evaporation',color:'#ffb454',info:{title:'Sun lifts the water',body:'The sun heats oceans and lakes. Liquid water turns into invisible vapour and rises into the air.',terms:['vapour','heat','evaporation']},quiz:{q:'What does the sun do to surface water?',options:['Evaporates it','Freezes it','Pulls it into rock','Makes it salty'],answer:0,hint:'Wet clothes dry in the sun for the same reason.'}},
 {name:'Condensation',color:'#9a86ff',info:{title:'Clouds form',body:'High up the air is cold. Vapour cools and condenses into tiny droplets that gather as clouds.',terms:['condensation','droplets','cloud']},quiz:{q:'Clouds form when vapour...',options:['Cools and condenses','Heats up','Sinks into soil','Turns to rock'],answer:0,hint:'Think of a cold glass sweating on a hot day.'}},
 {name:'Precipitation',color:'#62e6ff',info:{title:'Water falls back',body:'Droplets merge and grow heavy. They fall as rain, snow or hail.',terms:['rain','snow','hail']},quiz:{q:'Which of these is NOT precipitation?',options:['Evaporation','Rain','Snow','Hail'],answer:0,hint:'It goes up, not down.'}},
 {name:'Collection',color:'#74ffb8',info:{title:'Back to the start',body:'Water gathers in rivers, lakes and the ocean, or soaks into the ground. Then the sun lifts it again.',terms:['runoff','groundwater','ocean']},quiz:{q:'Where does most surface water collect?',options:['Oceans','Deserts','Clouds only','Mountain peaks'],answer:0,hint:'It covers most of the planet.'}}
 ],finale:{title:'Summit reached',body:'Evaporation, condensation, precipitation and collection keep water moving around the planet.'}}
};
Object.assign(WORLDS,extra);
function pickWorld(q){q=q.toLowerCase().trim();for(const k of Object.keys(extra)){const w=WORLDS[k];if(q===w.title.toLowerCase()||q.indexOf((w.match||w.title).toLowerCase())>=0)return[k,true]}
  const ready={'java':'java','explain me the java concept':'java','photosynthesis':'photosynthesis','how does photosynthesis work?':'photosynthesis','the water cycle':'water','water cycle':'water'};
  if(ready[q])return[ready[q],true];
  if(opts.onBuild)return[null,false];
  if(/java|jvm|class|object|oop|inherit/.test(q))return['java',true];
  if(/photo|plant|leaf|chloro|biolog/.test(q))return['photosynthesis',true];
  if(/water|rain|cloud|evapor|cycle/.test(q))return['water',true];
  return['java',false];}

/* ---------------- shop catalogue ---------------- */
const SUITS=[['orange','#ff8a5c',0],['cyan','#38d6ff',40],['lime','#8be04a',40],['pink','#ff6fa8',40],['purple','#9a6bff',40],['red','#e5394a',40],['yellow','#ffd23f',40],['white','#f3f3f7',60],['black','#2b2b36',60]];
const VISORS=[['sky','#8be8ff',0,'Classic sky tint'],['gold','#ffd25a',90,'Warm gold glass'],['rose','#ff9acb',60,'Rose glass'],['shades','#15151f',60,'Dark shades with a glare']];
const CATALOG={
 ride:[
  {id:'ride_none',name:'On foot',desc:'Normal walking speed.',price:0,value:null},
  {id:'ride_skate',name:'Skateboard',desc:'+30% speed. Roll in style.',price:120,value:'skate',speed:1.3},
  {id:'ride_bike',name:'Bicycle',desc:'+65% speed. Pedal across the zones.',price:260,value:'bike',speed:1.65},
  {id:'ride_hover',name:'Hoverboard',desc:'+110% speed. Glides above the ground.',price:520,value:'hover',speed:2.1}],
 hat:[
  {id:'hat_none',name:'No hat',desc:'Bare head.',price:0,value:null},
  {id:'hat_cap',name:'Red cap',desc:'A sporty cap with a long brim.',price:80,value:'cap'},
  {id:'hat_prop',name:'Propeller beanie',desc:'The blades really spin.',price:120,value:'prop'},
  {id:'hat_wizard',name:'Wizard hat',desc:'Pointy, purple, starry.',price:150,value:'wizard'},
  {id:'hat_crown',name:'Golden crown',desc:'For the top of the board.',price:300,value:'crown'}],
 color:SUITS.map(s=>({id:'suit_'+s[0],name:s[0][0].toUpperCase()+s[0].slice(1)+' suit',desc:'Change your crewmate colour.',price:s[2],value:s[1]})),
 visor:VISORS.map(v=>({id:'visor_'+v[0],name:v[0][0].toUpperCase()+v[0].slice(1)+' visor',desc:v[3],price:v[2],value:v[1]})),
 pet:[
  {id:'pet_none',name:'No pet',desc:'Travel solo.',price:0,value:null},
  {id:'pet_chick',name:'Mini chick',desc:'A cube chick that hops behind you.',price:200,value:'chick'},
  {id:'pet_bot',name:'Mini bot',desc:'A tiny robot with a glowing eye.',price:350,value:'bot'}],
 perk:[
  {id:'perk_magnet',name:'Coin magnet',desc:'Pulls coins from much farther away.',price:150,value:'magnet'},
  {id:'perk_boost',name:'Score boost',desc:'+25% on every point you earn.',price:200,value:'boost'}]
};
const TABS=[['ride','Rides'],['hat','Hats'],['color','Suits'],['visor','Visors'],['pet','Pets'],['perk','Perks']];
const DEFAULT_LOOK={color:'#ff8a5c',visor:'#8be8ff',hat:null,ride:null,pet:null};

/* ---------------- persistence ---------------- */
const SAVE_KEY='learnverse.v2';
let save={wallet:150,life:0,owned:['ride_none','hat_none','suit_orange','visor_sky','pet_none'],look:Object.assign({},DEFAULT_LOOK),welcome:true,rev:0};
try{const raw=localStorage.getItem(SAVE_KEY);if(raw){const s=JSON.parse(raw);save=Object.assign(save,s);save.look=Object.assign({},DEFAULT_LOOK,s.look||{});save.welcome=false}}catch(e){}
let remoteT=0;
function snapshot(){return{wallet:save.wallet,life:save.life,owned:save.owned,look:save.look,rev:save.rev||0}}
function pushRemote(){clearTimeout(remoteT);remoteT=0;if(opts.store)try{opts.store.save(snapshot())}catch(e){}}
function persist(){save.rev=(save.rev||0)+1;try{localStorage.setItem(SAVE_KEY,JSON.stringify(save))}catch(e){}if(opts.store){clearTimeout(remoteT);remoteT=setTimeout(pushRemote,500)}}
const owns=id=>save.owned.indexOf(id)>=0;

/* ---------------- renderer ---------------- */
let renderer;
try{renderer=new THREE.WebGLRenderer({canvas:$('#gl'),antialias:true,powerPreference:'high-performance'});}catch(e){$('#nogl').hidden=false;return noop;}
renderer.outputEncoding=THREE.sRGBEncoding;
renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;
renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
const scene=new THREE.Scene();
scene.fog=new THREE.FogExp2(K('#b8566f'),0.0085);
const camera=new THREE.PerspectiveCamera(55,1,0.1,800);
let composer=null,bloom=null;
const Q={tier:'high',dyn:1};
const fly={mat:null};
function setupComposer(){
  let rt=null;
  try{if(renderer.capabilities.isWebGL2&&THREE.WebGLMultisampleRenderTarget){rt=new THREE.WebGLMultisampleRenderTarget(innerWidth,innerHeight,{type:THREE.HalfFloatType,format:THREE.RGBAFormat});rt.samples=4}}catch(e){rt=null}
  composer=new EffectComposer(renderer,rt||undefined);
  composer.addPass(new RenderPass(scene,camera));
  bloom=new UnrealBloomPass(new THREE.Vector2(innerWidth/2,innerHeight/2),0.7,0.55,0.82);
  composer.addPass(bloom);
  composer.addPass(new ShaderPass(GammaCorrectionShader));
}
setupComposer();
const PRCAP={high:2,medium:1.5,low:1};
function resize(){
  const w=$('#app').clientWidth,h=$('#app').clientHeight;
  const pr=Math.max(.5,Math.min(devicePixelRatio,PRCAP[Q.tier])*Q.dyn);
  renderer.setPixelRatio(pr);renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
  if(composer){composer.setPixelRatio(pr);composer.setSize(w,h)}
  if(fly.mat)fly.mat.uniforms.uScale.value=pr*h*.5;
}
on('resize',resize);

/* ---------------- sky, sun, stars, lights ---------------- */
const ENC='\n#include <encodings_fragment>\n';
const sky=new THREE.Mesh(new THREE.SphereGeometry(500,32,16),new THREE.ShaderMaterial({side:THREE.BackSide,depthWrite:false,fog:false,
  uniforms:{top:{value:K('#14103d')},mid:{value:K('#6a3290')},bot:{value:K('#ff8a5c')}},
  vertexShader:'varying vec3 vP;void main(){vP=normalize(position);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
  fragmentShader:'uniform vec3 top,mid,bot;varying vec3 vP;void main(){float h=clamp(vP.y,-.1,1.);vec3 c=mix(bot,mid,smoothstep(-.02,.26,h));c=mix(c,top,smoothstep(.22,.85,h));gl_FragColor=vec4(c,1.);'+ENC+'}'}));
sky.frustumCulled=false;scene.add(sky);
const sun=new THREE.Mesh(new THREE.BoxGeometry(46,46,6),new THREE.MeshBasicMaterial({color:K('#ffe0a8').multiplyScalar(1.6),fog:false,toneMapped:false}));sun.position.set(0,34,-420);scene.add(sun);
const halo=new THREE.Mesh(new THREE.CircleGeometry(100,48),new THREE.MeshBasicMaterial({color:K('#ff9a6a'),transparent:true,opacity:.26,fog:false,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false}));
halo.position.set(0,34,-418);scene.add(halo);
{const n=900,pos=new Float32Array(n*3),r=rng(7);for(let i=0;i<n;i++){const a=r()*Math.PI*2,e=Math.acos(1-r()*0.9),R=470;pos[i*3]=R*Math.sin(e)*Math.cos(a);pos[i*3+1]=Math.abs(R*Math.cos(e))*0.95+20;pos[i*3+2]=R*Math.sin(e)*Math.sin(a)}
 const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(pos,3));
 const st=new THREE.Points(g,new THREE.PointsMaterial({color:K('#fff4e0'),size:1.6,sizeAttenuation:false,transparent:true,opacity:.75,fog:false,depthWrite:false}));st.frustumCulled=false;scene.add(st)}
scene.add(new THREE.HemisphereLight(K('#a58ae0'),K('#16363c'),0.85));
const dir=new THREE.DirectionalLight(K('#ffb27a'),1.9);
dir.castShadow=true;dir.shadow.mapSize.set(2048,2048);
Object.assign(dir.shadow.camera,{left:-34,right:34,top:34,bottom:-34,near:1,far:150});dir.shadow.bias=-0.0006;dir.shadow.normalBias=0.04;dir.shadow.camera.updateProjectionMatrix();
scene.add(dir);scene.add(dir.target);

/* ---------------- path ---------------- */
const CP=[[0,0,6],[0,0,-30],[16,0,-70],[-14,0,-115],[10,0,-160],[-6,0,-205],[0,0,-245],[0,0,-280]].map(a=>new THREE.Vector3(a[0],a[1],a[2]));
const curve=new THREE.CatmullRomCurve3(CP,false,'catmullrom',0.5);
const N=700,S=[],TG=[];
for(let i=0;i<=N;i++){const t=i/N;S.push(curve.getPointAt(t));TG.push(curve.getTangentAt(t))}
function nearest(px,pz,from,win){let b=-1,bd=1e9;const a=Math.max(0,from-win),z=Math.min(N,from+win);for(let i=a;i<=z;i++){const dx=px-S[i].x,dz=pz-S[i].z,d=dx*dx+dz*dz;if(d<bd){bd=d;b=i}}return{i:b,d:Math.sqrt(bd)}}
function nearestAll(px,pz){return nearest(px,pz,N/2,N/2+1)}

function canvasTex(w,h,draw,repeat,pixel){const c=document.createElement('canvas');c.width=w;c.height=h;draw(c.getContext('2d'),w,h);const t=new THREE.CanvasTexture(c);t.encoding=THREE.sRGBEncoding;t.anisotropy=4;if(repeat){t.wrapS=t.wrapT=THREE.RepeatWrapping;t.repeat.set(repeat[0],repeat[1])}if(pixel){t.magFilter=THREE.NearestFilter;t.minFilter=THREE.NearestMipmapLinearFilter}return t}
/* minecraft-style grass: 16px texture, nearest filtering, low contrast so it never sparkles */
const groundTex=canvasTex(16,16,(x,w,h)=>{const r=rng(3);for(let j=0;j<h;j++)for(let i=0;i<w;i++){x.fillStyle='hsl('+(170+r()*10)+',34%,'+(23+r()*5)+'%)';x.fillRect(i,j,1,1)}},[120,140],true);
const ground=new THREE.Mesh(new THREE.PlaneGeometry(700,800),new THREE.MeshStandardMaterial({map:groundTex,roughness:1,metalness:0}));
ground.rotation.x=-Math.PI/2;ground.position.set(0,0,-130);ground.receiveShadow=true;scene.add(ground);
function strip(w,y,mat,uvs){const pos=[],uv=[],nor=[],idx=[];
  for(let i=0;i<=N;i++){const p=S[i],t=TG[i],nx=-t.z,nz=t.x;pos.push(p.x+nx*w/2,y,p.z+nz*w/2,p.x-nx*w/2,y,p.z-nz*w/2);uv.push(0,i*uvs,1,i*uvs);nor.push(0,1,0,0,1,0)}
  for(let i=0;i<N;i++){const a=i*2;idx.push(a,a+1,a+2,a+1,a+3,a+2)}
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));g.setAttribute('normal',new THREE.Float32BufferAttribute(nor,3));g.setIndex(idx);
  const m=new THREE.Mesh(g,mat);m.receiveShadow=true;m.frustumCulled=false;return m}
const tileTex=canvasTex(128,128,(x,w,h)=>{x.fillStyle='#4a3f86';x.fillRect(0,0,w,h);x.strokeStyle='#ffb45488';x.lineWidth=3;x.strokeRect(2,2,w-4,h-4);x.fillStyle='#ffffff12';x.fillRect(8,8,w-16,h-16)},null);
tileTex.wrapS=tileTex.wrapT=THREE.RepeatWrapping;
scene.add(strip(7.4,0.04,new THREE.MeshStandardMaterial({map:tileTex,roughness:.55,metalness:.2,side:THREE.DoubleSide}),N*0.1));
const edgeMat=new THREE.MeshBasicMaterial({color:K('#ffb454').multiplyScalar(1.8),toneMapped:false,side:THREE.DoubleSide});
[-3.9,3.9].forEach(o=>{const pos=[],idx=[];for(let i=0;i<=N;i++){const p=S[i],t=TG[i],nx=-t.z,nz=t.x;pos.push(p.x+nx*(o-.12),0.07,p.z+nz*(o-.12),p.x+nx*(o+.12),0.07,p.z+nz*(o+.12))}
  for(let i=0;i<N;i++){const a=i*2;idx.push(a,a+1,a+2,a+1,a+3,a+2)}
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));g.setIndex(idx);const m=new THREE.Mesh(g,edgeMat);m.frustumCulled=false;scene.add(m)});

/* ---------------- scenery: voxel trees, crystals, lamps, clouds, sky islands (all instanced) ---------------- */
const BOX=new THREE.BoxGeometry(1,1,1);
const floaters=[];let clouds=null;
{const r=rng(11);
 const spots=[];let tries=0;while(spots.length<300&&tries<5000){tries++;const x=(r()-.5)*200,z=30-r()*330,nn=nearestAll(x,z);if(nn.d>15)spots.push([x,z,.85+r()*.6])}
 const nS=spots.length,mT=new THREE.MeshStandardMaterial({color:K('#5b3a4a'),roughness:1}),mL=new THREE.MeshStandardMaterial({color:0xffffff,roughness:.9,flatShading:true});
 const trunks=new THREE.InstancedMesh(BOX,mT,nS),l1=new THREE.InstancedMesh(BOX,mL,nS),l2=new THREE.InstancedMesh(BOX,mL,nS);
 const d=new THREE.Object3D(),c=new THREE.Color();
 spots.forEach((s,i)=>{const k=s[2],y0=r()*6.28;
   d.rotation.set(0,y0,0);d.scale.set(.9*k,3.4*k,.9*k);d.position.set(s[0],1.7*k,s[1]);d.updateMatrix();trunks.setMatrixAt(i,d.matrix);
   d.scale.set(3.6*k,2.4*k,3.6*k);d.position.y=4.1*k;d.updateMatrix();l1.setMatrixAt(i,d.matrix);
   d.scale.set(2.2*k,1.8*k,2.2*k);d.position.y=6.1*k;d.updateMatrix();l2.setMatrixAt(i,d.matrix);
   c.setHSL(.34+r()*.1,.5,.26+r()*.08).convertSRGBToLinear();l1.setColorAt(i,c);l2.setColorAt(i,c)});
 [trunks,l1,l2].forEach(m=>{m.frustumCulled=false;scene.add(m)});
 const cr=new THREE.InstancedMesh(new THREE.OctahedronGeometry(1,0),new THREE.MeshStandardMaterial({color:K('#ffffff'),emissive:K('#7d6bff'),emissiveIntensity:1.1,roughness:.25,metalness:.2,flatShading:true}),48);
 let k=0;while(k<48){const x=(r()-.5)*150,z=20-r()*300,nn=nearestAll(x,z);if(nn.d>11&&nn.d<30){const s=.6+r()*1.8;d.position.set(x,s*1.1,z);d.scale.set(s*.6,s*1.6,s*.6);d.rotation.set(0,r()*6,(r()-.5)*.3);d.updateMatrix();cr.setMatrixAt(k,d.matrix);c.setHSL(.7+r()*.2,.8,.6).convertSRGBToLinear();cr.setColorAt(k,c);k++}}
 cr.frustumCulled=false;scene.add(cr);
 const lamps=[];for(let i=20;i<N;i+=26){const p=S[i],t=TG[i],side=(i/26|0)%2?1:-1;lamps.push([p.x+(-t.z)*side*4.6,p.z+t.x*side*4.6])}
 const poles=new THREE.InstancedMesh(BOX,new THREE.MeshStandardMaterial({color:K('#2b2450'),roughness:.6}),lamps.length),bulbs=new THREE.InstancedMesh(BOX,new THREE.MeshBasicMaterial({color:K('#ffc36a').multiplyScalar(2),toneMapped:false}),lamps.length);
 lamps.forEach((l,i)=>{d.rotation.set(0,0,0);d.scale.set(.2,3,.2);d.position.set(l[0],1.5,l[1]);d.updateMatrix();poles.setMatrixAt(i,d.matrix);d.scale.set(.55,.55,.55);d.position.y=3.2;d.updateMatrix();bulbs.setMatrixAt(i,d.matrix)});
 [poles,bulbs].forEach(m=>{m.frustumCulled=false;scene.add(m)});
 clouds=new THREE.InstancedMesh(BOX,new THREE.MeshBasicMaterial({color:K('#ffd9d0'),transparent:true,opacity:.8,fog:false,depthWrite:false}),44);
 for(let i=0;i<44;i++){const a=r()*6.28,rad=140+r()*260;d.rotation.set(0,0,0);d.scale.set(18+r()*26,3,8+r()*10);d.position.set(Math.cos(a)*rad,62+r()*26,Math.sin(a)*rad-100);d.updateMatrix();clouds.setMatrixAt(i,d.matrix)}
 clouds.frustumCulled=false;scene.add(clouds);
 const mG=new THREE.MeshStandardMaterial({color:K('#2f8f78'),roughness:1,flatShading:true}),mD=new THREE.MeshStandardMaterial({color:K('#5b3a4a'),roughness:1,flatShading:true}),mS=new THREE.MeshStandardMaterial({color:K('#3a2c5c'),roughness:1,flatShading:true});
 for(let i=0;i<7;i++){const g=new THREE.Group(),sx=(i%2?1:-1)*(70+r()*60),sz=-r()*280,sy=14+r()*22,s=5+r()*5;
   const add=(m,w,h,dd,y)=>{const b=new THREE.Mesh(BOX,m);b.scale.set(w,h,dd);b.position.y=y;g.add(b)};
   add(mG,s*2,1,s*2,0);add(mD,s*1.8,1.4,s*1.8,-1.2);add(mS,s*1.3,1.6,s*1.3,-2.7);add(mS,s*.8,1.8,s*.8,-4.3);add(mS,s*.35,1.6,s*.35,-5.9);
   add(mT,.9,3.4,.9,2.7);add(mL,3.6,2.4,3.6,5.1);add(mL,2.2,1.8,2.2,7.1);
   g.position.set(sx,sy,sz);g.userData={y:sy,ph:r()*6};scene.add(g);floaters.push(g)}
}
/* fireflies animate on the GPU: one draw call, no per-frame JS */
{const n=240,r=rng(5),pos=new Float32Array(n*3),ph=new Float32Array(n);for(let i=0;i<n;i++){pos[i*3]=(r()-.5)*70;pos[i*3+1]=.6+r()*4;pos[i*3+2]=20-r()*320;ph[i]=r()*6}
 const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(pos,3));g.setAttribute('ph',new THREE.BufferAttribute(ph,1));
 fly.mat=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,uniforms:{uTime:{value:0},uScale:{value:500},uColor:{value:K('#ffd48a').multiplyScalar(1.6)}},
  vertexShader:'attribute float ph;uniform float uTime,uScale;void main(){vec3 p=position+vec3(sin(uTime*.4+ph)*2.5,sin(uTime*.8+ph*2.)*.6,cos(uTime*.35+ph)*2.5);vec4 mv=modelViewMatrix*vec4(p,1.);gl_PointSize=min(24.,.9*uScale/-mv.z);gl_Position=projectionMatrix*mv;}',
  fragmentShader:'uniform vec3 uColor;void main(){float d=length(gl_PointCoord-.5)*2.;float a=smoothstep(1.,0.,d);gl_FragColor=vec4(uColor,a*a);'+ENC+'}'});
 const pts=new THREE.Points(g,fly.mat);pts.frustumCulled=false;scene.add(pts)}

/* ---------------- avatar: voxel crewmate (blocky like Minecraft, visor + backpack like Among Us) ---------------- */
const player={g:new THREE.Group(),heading:0,v:0,phase:0,rideY:0,speedMul:1,jy:0,vy:0};
const AV={bodyM:new THREE.MeshStandardMaterial({color:K('#ff8a5c'),roughness:.55}),darkM:new THREE.MeshStandardMaterial({color:K('#d96c42'),roughness:.6}),visorM:new THREE.MeshStandardMaterial({color:K('#8be8ff'),roughness:.08,metalness:.55,emissive:K('#8be8ff'),emissiveIntensity:.35}),hat:null,hatKind:undefined,ride:null,rideKind:undefined,petRoot:null,petKind:undefined,spin:[],wheels:[]};
function bx(parent,m,w,h,d,x,y,z,shadow){const b=new THREE.Mesh(BOX,m);b.scale.set(w,h,d);b.position.set(x,y,z);if(shadow!==false)b.castShadow=true;parent.add(b);return b}
{const g=player.g,body=AV.bodyM,dark=AV.darkM;
 bx(g,body,1.1,1.45,.9,0,1.55,0);bx(g,body,.94,.22,.78,0,2.38,0);
 bx(g,AV.visorM,.8,.46,.14,0,2.0,-.5);
 bx(g,new THREE.MeshBasicMaterial({color:0xffffff,toneMapped:false}),.18,.08,.02,-.22,2.14,-.58,false);
 bx(g,dark,.86,.95,.34,0,1.5,.62);
 const mkLeg=x=>{const p=new THREE.Group();p.position.set(x,.82,0);g.add(p);bx(p,dark,.44,.74,.5,0,-.37,0);return p};
 player.legL=mkLeg(-.28);player.legR=mkLeg(.28);
 AV.hatAnchor=new THREE.Group();AV.hatAnchor.position.set(0,2.5,0);g.add(AV.hatAnchor);
 AV.rideAnchor=new THREE.Group();g.add(AV.rideAnchor);
 scene.add(g)}
function tint(hex){const c=K(hex);AV.bodyM.color.copy(c);AV.darkM.color.copy(c.clone().multiplyScalar(.74))}
function stdM(c,e,extra){return new THREE.MeshStandardMaterial(Object.assign({color:K(c),roughness:.5,flatShading:true,emissive:e?K(e):new THREE.Color(0),emissiveIntensity:e?.8:0},extra||{}))}
function buildHat(kind){
  const g=new THREE.Group();
  if(kind==='cap'){const d=new THREE.Mesh(new THREE.SphereGeometry(.62,14,8,0,Math.PI*2,0,Math.PI/2),stdM('#e5394a'));d.scale.set(1,.85,1);d.castShadow=true;g.add(d);bx(g,stdM('#f3f3f7'),.8,.08,.6,0,.02,-.62);bx(g,stdM('#f3f3f7'),.12,.12,.12,0,.55,0)}
  else if(kind==='prop'){const d=new THREE.Mesh(new THREE.SphereGeometry(.6,14,8,0,Math.PI*2,0,Math.PI/2),stdM('#38d6ff'));d.castShadow=true;g.add(d);bx(g,stdM('#ffd23f'),.07,.3,.07,0,.7,0);const sp=new THREE.Group();sp.position.y=.88;bx(sp,stdM('#ff6fa8'),1.1,.04,.18,0,0,0);bx(sp,stdM('#8be04a'),.18,.04,1.1,0,0,0);g.add(sp);AV.spin.push(sp)}
  else if(kind==='wizard'){const c=new THREE.Mesh(new THREE.ConeGeometry(.55,1.4,10),stdM('#6b3fd6'));c.position.y=.8;c.rotation.z=.12;c.castShadow=true;g.add(c);const b=new THREE.Mesh(new THREE.CylinderGeometry(.98,.98,.07,16),stdM('#5430b4'));b.castShadow=true;g.add(b);[[.2,.5,-.42],[-.25,.9,-.3],[.05,1.2,-.1]].forEach(p=>bx(g,stdM('#ffd25a','#ffb020'),.12,.12,.04,p[0],p[1],p[2],false))}
  else if(kind==='crown'){const r=new THREE.Mesh(new THREE.CylinderGeometry(.5,.56,.3,8),stdM('#ffc766','#ff9d20'));r.position.y=.12;r.castShadow=true;g.add(r);for(let i=0;i<5;i++){const a=i/5*6.283,c=new THREE.Mesh(new THREE.ConeGeometry(.12,.36,4),stdM('#ffc766','#ff9d20'));c.position.set(Math.cos(a)*.44,.46,Math.sin(a)*.44);g.add(c)}}
  return g}
function buildRide(kind){
  const g=new THREE.Group();AV.wheels=[];
  const M=(c,e)=>stdM(c,e,{flatShading:false,metalness:.3,emissiveIntensity:e?.9:0});
  const glow=(c)=>new THREE.MeshBasicMaterial({color:K(c).multiplyScalar(2.4),toneMapped:false});
  if(kind==='skate'){bx(g,M('#2b2b36'),1.05,.12,2.5,0,.3,0);bx(g,glow('#ff6fa8'),.9,.02,.3,0,.37,-.7,false);
    [[-.5,-.8],[.5,-.8],[-.5,.8],[.5,.8]].forEach(p=>{const w=new THREE.Mesh(new THREE.CylinderGeometry(.2,.2,.16,12),M('#f3f3f7'));w.rotation.z=Math.PI/2;w.position.set(p[0],.2,p[1]);w.castShadow=true;g.add(w);AV.wheels.push(w)});player.rideY=.36}
  else if(kind==='bike'){
    [-.9,.9].forEach(z=>{const w=new THREE.Mesh(new THREE.TorusGeometry(.5,.07,8,22),M('#2b2b36'));w.rotation.y=Math.PI/2;w.position.set(0,.58,z);w.castShadow=true;g.add(w);AV.wheels.push(w);bx(g,M('#ffb454'),.1,.1,.1,0,.58,z,false)});
    bx(g,M('#e5394a'),.1,.1,1.7,0,.82,0);bx(g,M('#e5394a'),.1,.7,.1,0,.6,.5);bx(g,M('#2b2b36'),.34,.1,.5,0,1.08,.5);bx(g,M('#e5394a'),.1,.55,.1,0,.95,-.85);bx(g,M('#2b2b36'),.8,.08,.08,0,1.25,-.85);player.rideY=.4}
  else if(kind==='hover'){bx(g,M('#3a3f6b'),1.2,.16,2.8,0,.4,0);bx(g,glow('#62e6ff'),1.0,.05,2.6,0,.29,0,false);bx(g,glow('#62e6ff'),1.2,.04,.1,0,.49,-1.35,false);player.rideY=.78}
  return g}
function buildPet(kind){
  const g=new THREE.Group();const M=(c,e)=>stdM(c,e,{metalness:kind==='bot'?.5:0,emissiveIntensity:e?1:0});
  if(kind==='chick'){bx(g,M('#ffd23f'),.62,.6,.62,0,.5,0);bx(g,M('#ff8a3d'),.22,.12,.2,0,.5,-.4);bx(g,M('#1c1634'),.08,.1,.04,-.16,.62,-.32,false);bx(g,M('#1c1634'),.08,.1,.04,.16,.62,-.32,false);bx(g,M('#ff8a3d'),.08,.18,.08,-.15,.1,0);bx(g,M('#ff8a3d'),.08,.18,.08,.15,.1,0)}
  else{bx(g,M('#9aa3b8'),.64,.5,.58,0,.52,0);bx(g,M('#cfd6e6'),.46,.3,.46,0,.92,0);bx(g,new THREE.MeshBasicMaterial({color:K('#62e6ff').multiplyScalar(2.4),toneMapped:false}),.34,.1,.04,0,.95,-.24,false);bx(g,M('#9aa3b8'),.04,.3,.04,0,1.2,0);bx(g,M('#ff6fa8','#ff6fa8'),.1,.1,.1,0,1.4,0);bx(g,M('#4a5068'),.16,.2,.16,-.18,.12,0);bx(g,M('#4a5068'),.16,.2,.16,.18,.12,0)}
  return g}
function applyLook(l){
  tint(l.color);AV.visorM.color.copy(K(l.visor));AV.visorM.emissive.copy(K(l.visor));AV.visorM.emissiveIntensity=l.visor==='#15151f'?.05:.35;
  if(AV.hatKind!==l.hat){if(AV.hat){AV.hatAnchor.remove(AV.hat);AV.hat=null}AV.spin=[];if(l.hat){AV.hat=buildHat(l.hat);AV.hatAnchor.add(AV.hat)}AV.hatKind=l.hat}
  if(AV.rideKind!==l.ride){if(AV.ride){AV.rideAnchor.remove(AV.ride);AV.ride=null}player.rideY=0;AV.wheels=[];if(l.ride){AV.ride=buildRide(l.ride);AV.rideAnchor.add(AV.ride)}AV.rideKind=l.ride;AV.rideAnchor.position.y=-player.rideY}
  if(AV.petKind!==l.pet){if(AV.petRoot){scene.remove(AV.petRoot);AV.petRoot=null}if(l.pet){AV.petRoot=buildPet(l.pet);AV.petRoot.position.copy(player.g.position);scene.add(AV.petRoot)}AV.petKind=l.pet}
  const R=CATALOG.ride.find(r=>r.value===l.ride);player.speedMul=R&&R.speed?R.speed:1;
  const rl=$('#rideLbl');if(rl)rl.textContent=R&&R.value?R.name+' · '+Math.round(R.speed*100-100)+'% faster':'';
}
let look=Object.assign({},save.look);
function placePlayer(i){const p=S[i],t=TG[i];player.g.position.set(p.x,0,p.z);player.heading=Math.atan2(-t.x,-t.z);player.g.rotation.y=player.heading;player.v=0;if(AV.petRoot)AV.petRoot.position.set(p.x+1.4,0,p.z+2)}

/* ---------------- world per topic ---------------- */
const world=new THREE.Group();scene.add(world);let assemble=1;
const ZT=[.115,.295,.475,.655],GT=[.2,.38,.56,.74],FT=.925;
let T=null,zones=[],items=[],coins=[],billboards=[];
function disposeGroup(g){g.traverse(o=>{if(o.geometry&&o.geometry!==BOX&&o.geometry!==coinGeo)o.geometry.dispose();if(o.material&&o.material!==coinMat){(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>{if(m.map)m.map.dispose();m.dispose()})}});while(g.children.length)g.remove(g.children[0])}
function rr(x,a,b,w,h,r){x.beginPath();x.moveTo(a+r,b);x.arcTo(a+w,b,a+w,b+h,r);x.arcTo(a+w,b+h,a,b+h,r);x.arcTo(a,b+h,a,b,r);x.arcTo(a,b,a+w,b,r);x.closePath()}
function panelTex(label,title,color,w,h){
  return canvasTex(w,h,(x)=>{
    x.fillStyle='rgba(18,10,48,.82)';rr(x,6,6,w-12,h-12,28);x.fill();x.lineWidth=5;x.strokeStyle=color;rr(x,6,6,w-12,h-12,28);x.stroke();
    x.fillStyle=color;x.font='700 34px "Chakra Petch",sans-serif';x.textBaseline='top';x.fillText(label.toUpperCase(),44,40);
    x.fillStyle='#fff2e3';x.font='700 70px "Chakra Petch",sans-serif';
    const words=title.split(' ');let line='',y=104;const lines=[];words.forEach(wd=>{const t=line?line+' '+wd:wd;if(x.measureText(t).width>w-88&&line){lines.push(line);line=wd}else line=t});lines.push(line);
    lines.slice(0,2).forEach(l=>{x.fillText(l,44,y);y+=78});
  });
}
function billboard(label,title,color,x,y,z,wid){const tex=panelTex(label,title,color,1024,400);const m=new THREE.Mesh(new THREE.PlaneGeometry(wid,wid*400/1024),new THREE.MeshBasicMaterial({map:tex,transparent:true,depthWrite:false,toneMapped:false,fog:false}));m.position.set(x,y,z);world.add(m);billboards.push(m);return m}
const barrierVS='varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}';
const barrierFS='uniform float uTime,uOpen;uniform vec3 uColor;varying vec2 vUv;void main(){vec2 p=vUv*vec2(14.,7.);float g=smoothstep(.44,.5,abs(fract(p.x)-.5))*.5+smoothstep(.44,.5,abs(fract(p.y)-.5))*.5;float sc=.5+.5*sin(vUv.y*46.-uTime*3.);float e=smoothstep(0.,.05,vUv.x)*smoothstep(1.,.95,vUv.x);float a=(.16+g*.5+sc*.12)*e*(1.-uOpen);gl_FragColor=vec4(uColor*(1.5+g),a);'+ENC+'}';
const portalFS='uniform float uTime;uniform vec3 uColor;varying vec2 vUv;void main(){vec2 q=vUv-.5;float r=length(q)*2.;float an=atan(q.y,q.x);float s=.5+.5*sin(an*6.+r*10.-uTime*2.2);float a=smoothstep(1.,.86,r)*(.28+.55*s*(1.-r*.6));gl_FragColor=vec4(uColor*(1.4+s),a);'+ENC+'}';
const coinGeo=new THREE.BoxGeometry(.7,.7,.2),coinMat=new THREE.MeshStandardMaterial({color:K('#ffd25a'),emissive:K('#ffb020'),emissiveIntensity:.9,metalness:.6,roughness:.25,flatShading:true});
function buildWorld(key){
  disposeGroup(world);billboards=[];items=[];coins=[];zones=[];
  T=WORLDS[key];
  T.zones.forEach((z,zi)=>{
    const col=z.color,cc=K(col),ti=Math.round(ZT[zi]*N),p=S[ti],t=TG[ti],side=zi%2?1:-1,nx=-t.z,nz=t.x,sx=p.x+nx*side*9.5,sz=p.z+nz*side*9.5;
    const g=new THREE.Group();g.position.set(sx,0,sz);
    const base=new THREE.Mesh(new THREE.CylinderGeometry(3.4,3.7,.5,28),new THREE.MeshStandardMaterial({color:K('#241b4a'),roughness:.5,metalness:.3}));base.position.y=.25;base.receiveShadow=true;g.add(base);
    const ring=new THREE.Mesh(new THREE.TorusGeometry(3.25,.09,8,48),new THREE.MeshBasicMaterial({color:cc.clone().multiplyScalar(2),toneMapped:false}));ring.rotation.x=Math.PI/2;ring.position.y=.52;g.add(ring);
    const ped=new THREE.Mesh(new THREE.CylinderGeometry(.7,1,1.4,10),new THREE.MeshStandardMaterial({color:K('#3b2f6e'),roughness:.4,metalness:.4}));ped.position.y=1.2;ped.castShadow=true;g.add(ped);
    const cm=new THREE.MeshStandardMaterial({color:cc,emissive:cc,emissiveIntensity:1.2,roughness:.15,metalness:.2,flatShading:true});
    const crystal=new THREE.Mesh(new THREE.OctahedronGeometry(1.15,0),cm);crystal.scale.y=1.5;crystal.position.y=3.3;crystal.castShadow=true;g.add(crystal);
    const rm=new THREE.MeshBasicMaterial({color:cc.clone().multiplyScalar(1.8),toneMapped:false});
    const r1=new THREE.Mesh(new THREE.TorusGeometry(2,.05,6,40),rm);r1.position.y=3.3;g.add(r1);const r2=r1.clone();g.add(r2);
    const beamM=new THREE.MeshBasicMaterial({color:cc.clone().multiplyScalar(1.4),transparent:true,opacity:.2,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,toneMapped:false,fog:false});
    const beam=new THREE.Mesh(new THREE.CylinderGeometry(.5,1.4,34,16,1,true),beamM);beam.position.y=17;g.add(beam);
    const pl=new THREE.PointLight(cc,1.3,22,2);pl.position.y=4;g.add(pl);
    world.add(g);
    const bb=billboard('Station '+(zi+1)+' · '+z.name,z.info.title,col,sx,8.4,sz,9.2);
    items.push({type:'info',zi,pos:new THREE.Vector3(sx,0,sz),radius:7.5,done:false,crystal,r1,r2,cm,beamM,group:g,title:z.info.title,bb});
    const gi=Math.round(GT[zi]*N),gp=S[gi],gt=TG[gi];
    const gg=new THREE.Group();gg.position.set(gp.x,0,gp.z);gg.rotation.y=Math.atan2(gt.x,gt.z);
    const pm=new THREE.MeshStandardMaterial({color:K('#241b4a'),roughness:.4,metalness:.4}),stm=new THREE.MeshBasicMaterial({color:cc.clone().multiplyScalar(2),toneMapped:false});
    [-7.2,7.2].forEach(x=>{const pi=new THREE.Mesh(BOX,pm);pi.scale.set(1.2,8.4,1.2);pi.position.set(x,4.2,0);pi.castShadow=true;gg.add(pi);const st=new THREE.Mesh(BOX,stm);st.scale.set(.3,7.4,.3);st.position.set(x,4.2,.66);gg.add(st)});
    const lintel=new THREE.Mesh(BOX,pm);lintel.scale.set(16.2,1,1.2);lintel.position.set(0,8.4,0);lintel.castShadow=true;gg.add(lintel);
    const bm=new THREE.ShaderMaterial({transparent:true,depthWrite:false,side:THREE.DoubleSide,blending:THREE.AdditiveBlending,uniforms:{uTime:{value:0},uOpen:{value:0},uColor:{value:cc}},vertexShader:barrierVS,fragmentShader:barrierFS});
    const barrier=new THREE.Mesh(new THREE.PlaneGeometry(14,7.6),bm);barrier.position.y=3.9;gg.add(barrier);
    world.add(gg);
    const gb=billboard('Quiz gate '+(zi+1),z.name,col,gp.x,11.8,gp.z,7.6);
    items.push({type:'gate',zi,pos:new THREE.Vector3(gp.x,0,gp.z),radius:9,done:false,open:0,bm,idx:gi,group:gg,bb:gb});
    zones.push({info:false,quiz:false,tries:0,wrong:0,pts:0});
  });
  const fi=Math.round(FT*N),fp=S[fi],fg=new THREE.Group();fg.position.set(fp.x,0,fp.z);
  const plat=new THREE.Mesh(new THREE.CylinderGeometry(7,7.6,.6,32),new THREE.MeshStandardMaterial({color:K('#2b2160'),roughness:.4,metalness:.4}));plat.position.y=.3;plat.receiveShadow=true;fg.add(plat);
  const gold=K('#ffc766');
  const portal=new THREE.Mesh(new THREE.TorusGeometry(4.2,.28,10,64),new THREE.MeshBasicMaterial({color:gold.clone().multiplyScalar(2.2),toneMapped:false}));portal.position.y=5.2;fg.add(portal);
  const pm2=new THREE.ShaderMaterial({transparent:true,depthWrite:false,side:THREE.DoubleSide,blending:THREE.AdditiveBlending,uniforms:{uTime:{value:0},uColor:{value:gold}},vertexShader:barrierVS,fragmentShader:portalFS});
  const swirl=new THREE.Mesh(new THREE.CircleGeometry(4.1,40),pm2);swirl.position.y=5.2;fg.add(swirl);
  const fb=new THREE.Mesh(new THREE.CylinderGeometry(1.2,3.6,50,20,1,true),new THREE.MeshBasicMaterial({color:gold.clone().multiplyScalar(1.5),transparent:true,opacity:.22,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,toneMapped:false,fog:false}));fb.position.y=25;fg.add(fb);
  const fl=new THREE.PointLight(gold,2,34,2);fl.position.y=5;fg.add(fl);
  fg.rotation.y=Math.atan2(TG[fi].x,TG[fi].z);world.add(fg);
  const fbb=billboard('Final station',T.finale.title,'#ffc766',fp.x,13.2,fp.z,10);
  items.push({type:'finale',pos:new THREE.Vector3(fp.x,0,fp.z),radius:7.5,done:false,portal,pm2,group:fg,bb:fbb});
  const r=rng(21);
  for(let k=0;k<30;k++){const t=.03+k/30*.9;if([...ZT,...GT,FT].some(v=>Math.abs(v-t)<.025))continue;const i=Math.round(t*N),p=S[i],tg=TG[i],o=(r()-.5)*5;
    const m=new THREE.Mesh(coinGeo,coinMat);m.position.set(p.x+(-tg.z)*o,1.5,p.z+tg.x*o);m.castShadow=true;world.add(m);coins.push(m)}
}

/* ---------------- state / HUD ---------------- */
const state={mode:'topic',streak:0,coins:0,wrong:0,reading:0,quizPts:0,coinPts:0,run:0,worldKey:'java',req:'',orbit:0,current:null};
const keys={up:false,down:false,left:false,right:false};
const $pts=$('#pts'),$lvl=$('#lvl'),$stk=$('#stk');
const levelOf=()=>1+Math.floor(save.life/150);
function fmtPts(pop){$pts.textContent=save.wallet;$lvl.textContent=levelOf();$stk.textContent=state.streak;$('#lbar').style.width=((save.life%150)/150*100)+'%';$('#tWallet').textContent=save.wallet;$('#sWallet').textContent=save.wallet;if(pop){$pts.classList.remove('pop');void $pts.offsetWidth;$pts.classList.add('pop')}}
function toast(msg){const e=$('#toast');e.textContent=msg;e.classList.add('on');clearTimeout(toast.t);toast.t=setTimeout(()=>e.classList.remove('on'),3400)}
const v3=new THREE.Vector3();
function floatText(txt,wp){v3.copy(wp);v3.y+=3;v3.project(camera);const a=$('#app'),x=(v3.x*.5+.5)*a.clientWidth,y=(-v3.y*.5+.5)*a.clientHeight,e=document.createElement('div');e.className='float';e.textContent=txt;e.style.left=x+'px';e.style.top=y+'px';$('#hud').appendChild(e);setTimeout(()=>e.remove(),1500)}
function addPts(n,label,wp,kind){const b=owns('perk_boost')?Math.round(n*1.25):n;save.wallet+=b;save.life+=b;state.run+=b;if(kind==='read')state.reading+=b;if(kind==='quiz')state.quizPts+=b;if(kind==='coin')state.coinPts+=b;fmtPts(true);persist();if(wp)floatText('+'+b+(label?' '+label:''),wp)}
function buildStepper(){const s=$('#stepper');s.innerHTML='';T.zones.forEach((z,i)=>{const sg=document.createElement('div');sg.className='seg';sg.style.setProperty('--c',z.color);sg.innerHTML='<i class="dot" data-i="'+i+'" data-t="i"></i><i class="dot q" data-i="'+i+'" data-t="q"></i>';s.appendChild(sg)});const f=document.createElement('span');f.className='flag';f.textContent='SUMMIT';s.appendChild(f)}
function refreshStepper(){$('#stepper').querySelectorAll('.dot').forEach(d=>{const z=zones[+d.dataset.i];d.classList.toggle('on',d.dataset.t==='i'?z.info:z.quiz)})}
function setZoneLabel(){const i=state.current;$('#hZone').textContent=i==null?'Follow the glowing path ahead':('Zone '+(i+1)+' of '+T.zones.length+' · '+T.zones[i].name)}

/* ---------------- audio ---------------- */
let actx=null,soundOn=true;
function blip(f,d,type,g,slide){if(!soundOn)return;try{actx=actx||new (window.AudioContext||window.webkitAudioContext)();const o=actx.createOscillator(),v=actx.createGain();o.type=type||'sine';o.frequency.value=f;if(slide)o.frequency.exponentialRampToValueAtTime(slide,actx.currentTime+d);v.gain.value=g||.06;v.gain.exponentialRampToValueAtTime(.0001,actx.currentTime+d);o.connect(v);v.connect(actx.destination);o.start();o.stop(actx.currentTime+d)}catch(e){}}
const sfx={coin:()=>blip(880,.12,'triangle',.05,1320),ok:()=>{blip(523,.15,'triangle');setTimeout(()=>blip(784,.25,'triangle'),110)},no:()=>blip(180,.25,'sawtooth',.05,120),read:()=>blip(660,.18,'sine',.05,990),buy:()=>{blip(660,.1,'square',.035);setTimeout(()=>blip(990,.2,'square',.035),90)}};

/* ---------------- particles ---------------- */
const BN=420,bpos=new Float32Array(BN*3),bcol=new Float32Array(BN*3),bvel=new Float32Array(BN*3),blife=new Float32Array(BN);let bi=0,bAlive=0;
const bg=new THREE.BufferGeometry();bg.setAttribute('position',new THREE.BufferAttribute(bpos,3));bg.setAttribute('color',new THREE.BufferAttribute(bcol,3));
for(let i=0;i<BN;i++)bpos[i*3+1]=-50;
const bursts=new THREE.Points(bg,new THREE.PointsMaterial({size:.55,vertexColors:true,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false,fog:false}));bursts.frustumCulled=false;scene.add(bursts);
function burst(pos,hex,n){const c=K(hex);for(let k=0;k<n;k++){const i=bi++%BN,a=Math.random()*6.28,e=Math.random()*1.4,s=3+Math.random()*7;bpos[i*3]=pos.x;bpos[i*3+1]=pos.y+2;bpos[i*3+2]=pos.z;bvel[i*3]=Math.cos(a)*Math.cos(e)*s;bvel[i*3+1]=Math.sin(e)*s+3;bvel[i*3+2]=Math.sin(a)*Math.cos(e)*s;blife[i]=1.2;bcol[i*3]=c.r*2;bcol[i*3+1]=c.g*2;bcol[i*3+2]=c.b*2}bAlive=1.4}
function updBursts(dt){if(bAlive<=0)return;bAlive-=dt;for(let i=0;i<BN;i++){if(blife[i]>0){blife[i]-=dt;bpos[i*3]+=bvel[i*3]*dt;bpos[i*3+1]+=bvel[i*3+1]*dt;bpos[i*3+2]+=bvel[i*3+2]*dt;bvel[i*3+1]-=9*dt;bcol[i*3]*=.965;bcol[i*3+1]*=.965;bcol[i*3+2]*=.965;if(blife[i]<=0)bpos[i*3+1]=-50}}bg.attributes.position.needsUpdate=true;bg.attributes.color.needsUpdate=true}

/* ---------------- modals ---------------- */
const modal=$('#modal'),card=$('#card');
function openModal(color){card.style.setProperty('--c',color||'');modal.classList.add('on');state.mode='modal';Object.keys(keys).forEach(k=>keys[k]=false);root.querySelectorAll('.pad button').forEach(b=>b.classList.remove('down'))}
function closeModal(){modal.classList.remove('on');state.mode='play'}
function el(tag,cls,txt){const e=document.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e}
function openInfo(it,back){
  const z=T.zones[it.zi],i=z.info;card.innerHTML='';card._keys=null;
  card.appendChild(el('div','eyebrow','Station '+(it.zi+1)+' · '+z.name));card.appendChild(el('h2','',i.title));card.appendChild(el('p','',i.body));
  if(i.code)card.appendChild(el('pre','',i.code));
  if(i.extra&&i.extra.length){const xs=el('div','extras');i.extra.forEach(x=>{const r=el('div','extra');r.appendChild(el('b','',x.label));r.appendChild(el('span','',x.text));xs.appendChild(r)});card.appendChild(xs)}
  const tm=el('div','terms');i.terms.forEach(t=>tm.appendChild(el('span','term',t)));card.appendChild(tm);
  const first=!zones[it.zi].info;
  const foot=el('div','cardfoot');foot.appendChild(el('div','worth',first?'First read earns 10 points':'Already read'));
  const b=el('button','btn',first?'Got it':'Close');b.addEventListener('click',()=>{if(first){zones[it.zi].info=true;it.done=true;it.cm.emissive.set(K('#74ffb8'));it.cm.color.set(K('#74ffb8'));it.beamM.opacity=.08;addPts(10,'read',it.pos,'read');sfx.read();burst(it.pos,'#74ffb8',40);refreshStepper();toast('Walk on to the glowing gate and answer the quiz')}closeModal();if(back)back()});foot.appendChild(b);card.appendChild(foot);
  openModal(z.color);b.focus();
}
function pointsFor(tries){return tries===0?100:tries===1?50:25}
function openQuiz(it){
  // A gate can ask several questions (the Meta quiz brings every question the study tools wrote). It opens after the last one.
  const zi=it.zi,z=T.zones[zi],zs=zones[zi],list=[z.quiz].concat(z.more||[]);
  zs.qi=zs.qi||0;
  function show(){
    const q=list[zs.qi],last=zs.qi===list.length-1;zs.tries=0;card.innerHTML='';
    const order=q.options.map((o,i)=>i);for(let i=order.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[order[i],order[j]]=[order[j],order[i]]}
    card.appendChild(el('div','eyebrow','Quiz gate '+(zi+1)+' · '+z.name+(list.length>1?' · question '+(zs.qi+1)+' of '+list.length:'')));card.appendChild(el('h2','',q.q));
    const opts=el('div','opts'),fb=el('div','fbk',''),foot=el('div','cardfoot'),worth=el('div','worth','Worth '+pointsFor(zs.tries)+' points');foot.appendChild(worth);
    const learn=el('button','btn ghost sm','Read the station first');learn.addEventListener('click',()=>{const si=items.find(x=>x.type==='info'&&x.zi===zi);if(si)openInfo(si,()=>openQuiz(it))});
    const later=el('button','btn ghost sm','Not yet');later.addEventListener('click',()=>closeModal());
    foot.appendChild(learn);foot.appendChild(later);
    const go=el('button','btn',last?'Open the gate':'Next question');go.hidden=true;foot.appendChild(go);
    const btns=order.map((oi,pos)=>{const b=el('button','opt');b.appendChild(el('span','key',String(pos+1)));b.appendChild(el('span','',q.options[oi]));b.dataset.ok=oi===q.answer?'1':'';b.addEventListener('click',()=>answer(b));opts.appendChild(b);return b});
    function answer(b){
      if(b.dataset.ok){
        const pts=pointsFor(zs.tries);btns.forEach(x=>{x.disabled=true});b.classList.add('ok');fb.className='fbk ok';fb.textContent='Correct! +'+(owns('perk_boost')?Math.round(pts*1.25):pts)+' points'+(q.why?'. '+q.why:'');
        if(zs.tries===0)state.streak++;else state.streak=0;addPts(pts,'',it.pos,'quiz');sfx.ok();
        burst(it.pos.clone().setY(2),z.color,last?120:50);worth.hidden=true;learn.hidden=true;later.hidden=true;go.hidden=false;go.focus();
        if(last){zs.quiz=true;it.done=true;refreshStepper()}
      }else{
        b.classList.add('no');b.disabled=true;zs.tries++;zs.wrong++;state.wrong++;state.streak=0;fmtPts();fb.className='fbk no';fb.textContent='Not quite. Hint: '+q.hint;worth.textContent='Worth '+pointsFor(zs.tries)+' points';sfx.no();
      }
    }
    go.addEventListener('click',()=>{
      if(!last){zs.qi++;show();return}
      closeModal();const n=zones.filter(x=>x.quiz).length;toast(n===zones.length?'All gates open. Reach the golden portal!':'Gate open. Zone '+(zi+1)+' complete.')});
    card.appendChild(opts);card.appendChild(fb);card.appendChild(foot);openModal(z.color);card._keys=btns;
  }
  show();
}
function openFinale(it){
  it.done=true;const stars=state.wrong===0?3:state.wrong<=2?2:1;
  card.innerHTML='';card._keys=null;card.appendChild(el('div','eyebrow',T.title+' · complete'));card.appendChild(el('h2','',T.finale.title));card.appendChild(el('p','',T.finale.body));
  const st=el('div','stars');for(let i=0;i<3;i++){st.innerHTML+='<svg viewBox="0 0 24 24"><path d="M12 2l3 6.5 7 .8-5.2 4.8 1.4 7L12 17.6 5.8 21l1.4-7L2 9.3l7-.8z" fill="'+(i<stars?'#ffc766':'rgba(255,255,255,.18)')+'"/></svg>'}card.appendChild(st);
  const sm=el('div','sum');[['Reading',state.reading],['Quizzes',state.quizPts],['Coins ('+state.coins+')',state.coinPts]].forEach(r=>{const d=el('div');d.appendChild(el('span','',r[0]));d.appendChild(el('span','',String(r[1])));sm.appendChild(d)});card.appendChild(sm);
  card.appendChild(el('div','big','+'+state.run));
  card.appendChild(el('div','worth',(state.wrong===0?'Perfect run. No wrong answers.':state.wrong+' wrong answer'+(state.wrong>1?'s':''))+' · Level '+levelOf()+' · '+save.wallet+' points in your wallet'));
  const foot=el('div','cardfoot');const a=el('button','btn ghost','Walk again'),s=el('button','btn ghost','Spend points'),b=el('button','btn','Explore another topic');foot.append(a,s,b);card.appendChild(foot);
  a.addEventListener('click',()=>{closeModal();startWorld(state.worldKey,state.req)});
  s.addEventListener('click',()=>{closeModal();openShop('play')});
  b.addEventListener('click',()=>{closeModal();toTopic()});
  openModal('#ffc766');burst(it.pos,'#ffc766',200);sfx.ok();
}

/* ---------------- shop ---------------- */
const shop={tab:'ride',sel:null,pv:null,from:'topic'};
const shopEl=$('#shop');
const ICON={
  suit:c=>'<svg viewBox="0 0 56 56"><rect x="14" y="8" width="28" height="34" rx="9" fill="'+c+'"/><rect x="20" y="42" width="7" height="8" fill="'+c+'"/><rect x="29" y="42" width="7" height="8" fill="'+c+'"/><rect x="22" y="16" width="22" height="11" rx="5" fill="#8be8ff"/><rect x="8" y="20" width="8" height="18" rx="3" fill="'+c+'" opacity=".75"/></svg>',
  visor:c=>'<svg viewBox="0 0 56 56"><rect x="6" y="16" width="44" height="24" rx="11" fill="'+c+'"/><rect x="12" y="20" width="10" height="5" rx="2" fill="#fff" opacity=".7"/></svg>',
  cap:'<svg viewBox="0 0 56 56"><path d="M12 36a16 16 0 0132 0z" fill="#e5394a"/><rect x="10" y="35" width="38" height="5" fill="#f3f3f7"/></svg>',
  prop:'<svg viewBox="0 0 56 56"><path d="M14 38a14 14 0 0128 0z" fill="#38d6ff"/><rect x="26" y="16" width="4" height="10" fill="#ffd23f"/><rect x="12" y="12" width="32" height="4" fill="#ff6fa8"/></svg>',
  wizard:'<svg viewBox="0 0 56 56"><path d="M28 6l14 30H14z" fill="#6b3fd6"/><rect x="8" y="35" width="40" height="5" rx="2" fill="#5430b4"/><rect x="26" y="20" width="5" height="5" fill="#ffd25a"/></svg>',
  crown:'<svg viewBox="0 0 56 56"><path d="M10 40V18l9 9 9-13 9 13 9-9v22z" fill="#ffc766"/><rect x="10" y="40" width="36" height="5" fill="#e09a30"/></svg>',
  none:'<svg viewBox="0 0 56 56"><circle cx="28" cy="28" r="16" fill="none" stroke="#c9b9d9" stroke-width="3"/><path d="M17 39L39 17" stroke="#c9b9d9" stroke-width="3"/></svg>',
  skate:'<svg viewBox="0 0 56 56"><rect x="6" y="30" width="44" height="6" rx="3" fill="#2b2b36"/><rect x="12" y="38" width="8" height="8" rx="4" fill="#f3f3f7"/><rect x="36" y="38" width="8" height="8" rx="4" fill="#f3f3f7"/><rect x="10" y="31" width="14" height="2" fill="#ff6fa8"/></svg>',
  bike:'<svg viewBox="0 0 56 56"><circle cx="14" cy="38" r="9" fill="none" stroke="#f3f3f7" stroke-width="3"/><circle cx="42" cy="38" r="9" fill="none" stroke="#f3f3f7" stroke-width="3"/><path d="M14 38l10-14h14l4 14M24 24l6 14" stroke="#e5394a" stroke-width="3" fill="none"/><rect x="34" y="18" width="10" height="3" fill="#f3f3f7"/></svg>',
  hover:'<svg viewBox="0 0 56 56"><rect x="6" y="26" width="44" height="7" rx="3" fill="#3a3f6b"/><rect x="10" y="36" width="36" height="4" rx="2" fill="#62e6ff"/><rect x="16" y="43" width="24" height="3" rx="1.5" fill="#62e6ff" opacity=".5"/></svg>',
  chick:'<svg viewBox="0 0 56 56"><rect x="14" y="14" width="28" height="26" fill="#ffd23f"/><rect x="24" y="26" width="9" height="6" fill="#ff8a3d"/><rect x="19" y="20" width="4" height="5" fill="#1c1634"/><rect x="33" y="20" width="4" height="5" fill="#1c1634"/><rect x="19" y="40" width="4" height="7" fill="#ff8a3d"/><rect x="33" y="40" width="4" height="7" fill="#ff8a3d"/></svg>',
  bot:'<svg viewBox="0 0 56 56"><rect x="14" y="24" width="28" height="20" fill="#9aa3b8"/><rect x="18" y="12" width="20" height="12" fill="#cfd6e6"/><rect x="21" y="16" width="14" height="4" fill="#62e6ff"/><rect x="26" y="5" width="3" height="8" fill="#9aa3b8"/><rect x="24" y="2" width="7" height="5" fill="#ff6fa8"/></svg>',
  magnet:'<svg viewBox="0 0 56 56"><path d="M14 12v20a14 14 0 0028 0V12" fill="none" stroke="#e5394a" stroke-width="9"/><rect x="9" y="8" width="10" height="9" fill="#f3f3f7"/><rect x="37" y="8" width="10" height="9" fill="#f3f3f7"/></svg>',
  boost:'<svg viewBox="0 0 56 56"><path d="M28 6l6 16h16l-13 10 5 17-14-10-14 10 5-17L6 22h16z" fill="#ffc766"/></svg>'
};
function iconFor(it,cat){if(cat==='color')return ICON.suit(it.value);if(cat==='visor')return ICON.visor(it.value);if(it.value===null)return ICON.none;return ICON[it.value]||ICON.none}
function isEquipped(it,cat){return cat!=='perk'&&look[cat]===it.value}
function renderShop(){
  $('#tabs').innerHTML='';
  TABS.forEach(t=>{const b=el('button','tab',t[1]);b.setAttribute('role','tab');b.setAttribute('aria-selected',t[0]===shop.tab);b.addEventListener('click',()=>{shop.tab=t[0];shop.sel=null;renderShop()});$('#tabs').appendChild(b)});
  const grid=$('#grid');grid.innerHTML='';
  CATALOG[shop.tab].forEach(it=>{
    const b=el('button','item');b.setAttribute('aria-pressed',!!(shop.sel&&shop.sel.id===it.id));
    b.innerHTML=iconFor(it,shop.tab);b.appendChild(el('span','n',it.name));b.appendChild(el('span','d',it.desc));
    const own=owns(it.id),eq=isEquipped(it,shop.tab);
    const tag=el('span','tag'+(eq?' eq':own?' own':''));if(eq)tag.textContent='Equipped';else if(own)tag.textContent=shop.tab==='perk'?'Active':'Owned';else{tag.innerHTML='<span class="coin"></span>'+it.price}
    b.appendChild(tag);b.addEventListener('click',()=>selectItem(it));grid.appendChild(b)});
  renderFoot();
}
function selectItem(it){shop.sel=it;if(shop.tab!=='perk'){shop.pv[shop.tab]=it.value;applyLook(shop.pv)}renderShop()}
function renderFoot(){
  const it=shop.sel,act=$('#sAct'),info=$('#sInfo');info.innerHTML='';
  if(!it){info.appendChild(el('span','','Tap an item to try it on. You only pay when you buy.'));act.textContent='Select an item';act.disabled=true;return}
  info.appendChild(el('b','',it.name));info.appendChild(el('span','',it.desc));
  const own=owns(it.id);
  if(own&&shop.tab==='perk'){act.textContent='Active';act.disabled=true}
  else if(own){const eq=isEquipped(it,shop.tab);act.textContent=eq?'Equipped':'Equip';act.disabled=eq}
  else if(save.wallet>=it.price){act.textContent='Buy for '+it.price+' points';act.disabled=false}
  else{act.textContent='Need '+(it.price-save.wallet)+' more points';act.disabled=true}
}
$('#sAct').addEventListener('click',()=>{
  const it=shop.sel;if(!it)return;const own=owns(it.id);
  if(!own){if(save.wallet<it.price)return;save.wallet-=it.price;save.owned.push(it.id);sfx.buy();burst(player.g.position,'#ffd25a',70);toast('Bought '+it.name)}
  else if(shop.tab!=='perk')toast(it.name+' equipped');
  if(shop.tab!=='perk'){look[shop.tab]=it.value;shop.pv=Object.assign({},look);save.look=Object.assign({},look);applyLook(look)}
  persist();fmtPts();renderShop();
});
function openShop(from){
  if(state.mode==='shop')return;
  shop.from=from;state.mode='shop';Object.keys(keys).forEach(k=>keys[k]=false);
  shop.pv=Object.assign({},look);shop.sel=null;shop.tab='ride';shopEl.classList.add('on');renderShop();fmtPts();$('#prompt').hidden=true;
  if(from==='topic')$('#topic').classList.add('gone');
}
function closeShop(){
  if(state.mode!=='shop')return;
  shopEl.classList.remove('on');applyLook(look);shop.pv=null;player.g.rotation.y=player.heading;
  if(shop.from==='topic'){state.mode='topic';$('#topic').classList.remove('gone')}else state.mode='play';
}
$('#sClose').addEventListener('click',closeShop);
$('#bShop').addEventListener('click',()=>{if(state.mode==='play')openShop('play')});
$('#tShop').addEventListener('click',()=>{if(state.mode==='topic')openShop('topic')});

/* ---------------- interaction ---------------- */
let near=null;
function interact(){
  if(state.mode!=='play'||!near)return;
  if(near.type==='info')openInfo(near);
  else if(near.type==='gate')openQuiz(near)
  else if(near.type==='finale'){if(zones.every(z=>z.quiz))openFinale(near);else toast('Open every quiz gate first')}
}
function findNear(){
  let best=null,bd=1e9;const p=player.g.position;
  for(const it of items){const d=Math.hypot(p.x-it.pos.x,p.z-it.pos.z);if(it.auto&&d>it.radius+4)it.auto=false;if(it.type==='gate'&&it.done)continue;if(d<it.radius&&d<bd){bd=d;best=it}}
  near=best;const pr=$('#prompt');
  if(best){pr.hidden=false;$('#promptT').textContent=best.type==='info'?'Read: '+best.title:best.type==='gate'?'Answer the question':(zones.every(z=>z.quiz)?'Enter the golden portal':'Finish every quiz gate first');$('#bAct').disabled=false;
    if(!best.auto&&(best.type==='gate'||(best.type==='finale'&&zones.every(z=>z.quiz)))){best.auto=true;interact()}}
  else{pr.hidden=true;$('#bAct').disabled=true}
}

/* ---------------- input ---------------- */
const KM={ArrowUp:'up',KeyW:'up',ArrowDown:'down',KeyS:'down',ArrowLeft:'left',KeyA:'left',ArrowRight:'right',KeyD:'right'};
on('keydown',e=>{
  if(state.mode==='play'){const k=KM[e.code];if(k){keys[k]=true;e.preventDefault();return}
    if(e.code==='KeyB'){openShop('play');return}
    if(e.code==='Space'){e.preventDefault();const a=root.activeElement;if(a&&a.blur)a.blur();if(!e.repeat)jump();return}
    if(e.code==='KeyE'||e.code==='Enter'){if(root.activeElement&&root.activeElement.tagName==='BUTTON'&&e.code!=='KeyE')return;e.preventDefault();interact()}}
  else if(state.mode==='shop'){if(e.code==='Escape'||(e.code==='KeyB'&&!/INPUT/.test((root.activeElement||{}).tagName||'')))closeShop()}
  else if(state.mode==='modal'&&/^Digit[1-4]$/.test(e.code)){const bs=card._keys;if(bs&&bs.length&&modal.classList.contains('on')){const b=bs[+e.code.slice(5)-1];if(b&&!b.disabled)b.click()}}
});
on('keyup',e=>{const k=KM[e.code];if(k)keys[k]=false});
on('blur',()=>Object.keys(keys).forEach(k=>keys[k]=false));
root.querySelectorAll('.pad button').forEach(b=>{const k=b.dataset.k;const on=ev=>{ev.preventDefault();keys[k]=true;b.classList.add('down');try{b.setPointerCapture(ev.pointerId)}catch(e){}};const off=()=>{keys[k]=false;b.classList.remove('down')};b.addEventListener('pointerdown',on);['pointerup','pointercancel','lostpointercapture'].forEach(n=>b.addEventListener(n,off))});
$('#bAct').addEventListener('click',interact);
$('#prompt').addEventListener('click',interact);
function jump(){if(state.mode!=='play'||player.jy>0.001)return;player.vy=8.6;player.jy=0.001;blip(420,.14,'square',.03,720)}
const bJump=$('#bJump');bJump.addEventListener('pointerdown',e=>{e.preventDefault();jump()});bJump.addEventListener('click',()=>jump());
$('#bSound').addEventListener('click',e=>{soundOn=!soundOn;e.currentTarget.setAttribute('aria-pressed',soundOn);e.currentTarget.textContent=soundOn?'Sound on':'Sound off'});
const TIERS=['high','medium','low'];
$('#bQual').addEventListener('click',()=>setTier(TIERS[(TIERS.indexOf(Q.tier)+1)%3]));
$('#bTopic').addEventListener('click',()=>{if(state.mode==='play')toTopic()});
function setTier(t){
  Q.tier=t;Q.dyn=1;$('#bQual').textContent='Quality: '+t[0].toUpperCase()+t.slice(1);
  renderer.shadowMap.enabled=t!=='low';const sz=t==='high'?2048:1024;if(dir.shadow.mapSize.x!==sz){dir.shadow.mapSize.set(sz,sz);if(dir.shadow.map){dir.shadow.map.dispose();dir.shadow.map=null}}
  resize();scene.traverse(o=>{if(o.material)(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>m.needsUpdate=true)});
}

/* ---------------- flow ---------------- */
function startWorld(key,req){
  state.worldKey=key;state.req=req;Object.assign(state,{streak:0,coins:0,wrong:0,reading:0,quizPts:0,coinPts:0,run:0,current:null});
  player.jy=0;player.vy=0;assemble=0;world.scale.y=.02;fmtPts();buildWorld(key);buildStepper();refreshStepper();placePlayer(14);lastIdx=14;applyLook(look);
  $('#hName').textContent=T.title;const rq=$('#hReq');rq.hidden=!req;rq.textContent='Requested: '+req.slice(0,40);
  setZoneLabel();state.mode='play';camState.follow=true;
  $('#topic').classList.add('gone');$('#hud').classList.add('on');perf.t=0;perf.acc=0;perf.n=0;
}
function toTopic(){state.mode='topic';camState.follow=false;near=null;$('#prompt').hidden=true;$('#hud').classList.remove('on');$('#topic').classList.remove('gone');$('#q').focus({preventScroll:true})}
let buildToken=0,retryTopic='';
function setBuild(p,stage){p=Math.max(.02,Math.min(1,p||0));$('#bFill').style.width=Math.round(p*100)+'%';$('#bPct').textContent=Math.round(p*100)+'%';if(stage)$('#bStage').textContent=stage}
function buildAi(topic){
  const my=++buildToken;retryTopic=topic;state.mode='building';$('#topic').classList.add('gone');
  $('#bTitle').textContent=topic.length>38?topic.slice(0,37)+'…':topic;$('#bBox').classList.remove('bad');$('#bErr').hidden=true;$('#bRetry').hidden=true;setBuild(.02,'Starting');$('#build').hidden=false;
  opts.onBuild(topic,(p,st)=>{if(my===buildToken)setBuild(p,st)}).then(w=>{
    if(my!==buildToken||dead)return;WORLDS.ai=w;setBuild(1,'Placing the stations');
    setTimeout(()=>{if(my!==buildToken||dead)return;$('#build').hidden=true;startWorld('ai','');toast('Your world is ready. Walk forward: quiz gates open by themselves. Space jumps.')},800);
  }).catch(err=>{if(my!==buildToken||dead)return;$('#bBox').classList.add('bad');$('#bStage').textContent='Could not build the world';$('#bErr').textContent=(err&&err.message)||'Something went wrong';$('#bErr').hidden=false;$('#bRetry').hidden=false});
}
$('#bCancel').addEventListener('click',()=>{buildToken++;$('#build').hidden=true;toTopic()});
$('#bRetry').addEventListener('click',()=>buildAi(retryTopic));
$('#tform').addEventListener('submit',e=>{
  e.preventDefault();const raw=$('#q').value.trim();if(!raw){$('#q').focus();return}
  const [key,hit]=pickWorld(raw);
  if(hit){startWorld(key,'');toast('Walk forward along the glowing path. Quiz gates open by themselves. Space jumps.');return}
  if(opts.onBuild){buildAi(raw);return}
  startWorld('java',raw);toast('No world for “'+raw.slice(0,40)+'” yet. Showing the Java demo.');
});
[...Object.keys(extra).map(k=>[WORLDS[k].title,WORLDS[k].title]),['Java','Explain me the Java concept'],['Photosynthesis','How does photosynthesis work?'],['Water cycle','The water cycle']].forEach(([l,v])=>{const b=el('button','chip',l);b.type='button';b.addEventListener('click',()=>{$('#q').value=v;$('#q').focus()});$('#chips').appendChild(b)});

/* ---------------- minimap ---------------- */
const mc=$('#mini'),mx=mc.getContext('2d');
function drawMini(){
  const W=mc.width,H=mc.height,sc=3.6;mx.clearRect(0,0,W,H);mx.save();mx.beginPath();mx.arc(W/2,H/2,W/2-2,0,7);mx.clip();mx.fillStyle='rgba(18,10,48,.8)';mx.fillRect(0,0,W,H);
  const p=player.g.position,h=player.heading,c=Math.cos(h),s=Math.sin(h);
  const tx=(x,z)=>{const dx=x-p.x,dz=z-p.z;return[W/2+(dx*c-dz*s)*sc,H/2+(dx*s+dz*c)*sc]};
  mx.strokeStyle='rgba(255,180,84,.7)';mx.lineWidth=9;mx.lineCap='round';mx.lineJoin='round';mx.beginPath();for(let i=0;i<=N;i+=8){const q=tx(S[i].x,S[i].z);i?mx.lineTo(q[0],q[1]):mx.moveTo(q[0],q[1])}mx.stroke();
  items.forEach(it=>{const q=tx(it.pos.x,it.pos.z);if(it.type==='info'){mx.fillStyle=T.zones[it.zi].color;mx.beginPath();mx.arc(q[0],q[1],it.done?6:9,0,7);mx.fill()}
    else if(it.type==='gate'&&!it.done){mx.fillStyle=T.zones[it.zi].color;mx.save();mx.translate(q[0],q[1]);mx.rotate(.78);mx.fillRect(-7,-7,14,14);mx.restore()}
    else if(it.type==='finale'){mx.fillStyle='#ffc766';mx.beginPath();mx.arc(q[0],q[1],11,0,7);mx.fill()}});
  mx.restore();mx.fillStyle='#fff';mx.beginPath();mx.moveTo(W/2,H/2-12);mx.lineTo(W/2+9,H/2+9);mx.lineTo(W/2-9,H/2+9);mx.closePath();mx.fill();
  mx.strokeStyle='rgba(255,236,214,.3)';mx.lineWidth=2;mx.beginPath();mx.arc(W/2,H/2,W/2-2,0,7);mx.stroke();
}

/* ---------------- loop ---------------- */
const camState={follow:false,pos:new THREE.Vector3(0,8,24),look:new THREE.Vector3(0,3,-10)};
const tp=new THREE.Vector3(),tl=new THREE.Vector3(),fwd=new THREE.Vector3();
const clock=new THREE.Clock();const perf={t:0,acc:0,n:0};let time=0,lastIdx=14,frameNo=0;
function constrain(px,pz){
  const nn=nearest(px,pz,lastIdx,60);let x=px,z=pz;
  if(nn.d>13){const s=S[nn.i],f=13/nn.d;x=s.x+(px-s.x)*f;z=s.z+(pz-s.z)*f}
  for(const it of items){if(it.type==='gate'&&!it.done&&nn.i>it.idx-5)return null}
  if(nn.i>=N-2)return null;lastIdx=nn.i;return[x,z];
}
function adapt(dt){
  if(state.mode!=='play')return;perf.t+=dt;perf.acc+=dt;perf.n++;
  if(perf.t>2){const avg=perf.acc/perf.n;perf.t=0;perf.acc=0;perf.n=0;
    if(avg>.034){if(Q.dyn>.65){Q.dyn=Math.max(.6,Q.dyn-.12);resize()}else if(Q.tier!=='low'){setTier(Q.tier==='high'?'medium':'low');toast('Switched to '+Q.tier+' quality for smoother movement')}}
    else if(avg<.02&&Q.dyn<1){Q.dyn=Math.min(1,Q.dyn+.08);resize()}}
}
function update(dt){
  time+=dt;frameNo++;
  if(assemble<1){assemble=Math.min(1,assemble+dt/1.3);world.scale.y=Math.max(.02,1-Math.pow(1-assemble,3))}
  const p=player.g.position,inShop=state.mode==='shop';
  if(state.mode==='play'){
    const turn=(keys.left?1:0)-(keys.right?1:0);player.heading+=turn*dt*2.3;
    const mul=player.speedMul||1,tv=((keys.up?1:0)*6.4*mul-(keys.down?1:0)*3.4);player.v+=(tv-player.v)*Math.min(1,dt*(mul>1.5?5:8));
    const nx=p.x-Math.sin(player.heading)*player.v*dt,nz=p.z-Math.cos(player.heading)*player.v*dt;
    if(Math.abs(player.v)>.01){const c=constrain(nx,nz);if(c){p.x=c[0];p.z=c[1]}else player.v*=.3}
    player.g.rotation.y=player.heading;
    const nn=nearest(p.x,p.z,lastIdx,60);let zi=null;for(let i=0;i<T.zones.length;i++){if(nn.i>=(i?GT[i-1]:0)*N-10&&nn.i<GT[i]*N+30)zi=i}
    if(zi!==state.current){state.current=zi;setZoneLabel()}
    const rad=owns('perk_magnet')?5.5:1.7;
    for(let i=coins.length-1;i>=0;i--){const c=coins[i],dx=p.x-c.position.x,dz=p.z-c.position.z,d=Math.hypot(dx,dz);
      if(d<rad&&d>.9&&rad>2){c.position.x+=dx*Math.min(1,dt*7);c.position.z+=dz*Math.min(1,dt*7)}
      if(d<1.4){world.remove(c);coins.splice(i,1);state.coins++;addPts(5,'',c.position,'coin');sfx.coin();burst(c.position,'#ffd25a',10)}}
    findNear();
  }else if(inShop){player.g.rotation.y+=dt*.6;player.v*=.9}
  const sp=Math.min(1,Math.abs(player.v)/6.4);player.phase+=player.v*dt*1.7;const sw=Math.sin(player.phase)*.85*sp;
  const riding=!!AV.rideKind;
  player.legL.rotation.x=riding?(AV.rideKind==='bike'?sw*.9:0):sw;player.legR.rotation.x=riding?(AV.rideKind==='bike'?-sw*.9:0):-sw;
  const bob=riding?(AV.rideKind==='hover'?Math.sin(time*2.4)*.12:0):Math.abs(Math.sin(player.phase))*.12*sp;
  if(player.jy>0||player.vy>0){player.vy-=24*dt;player.jy=Math.max(0,player.jy+player.vy*dt);if(player.jy===0)player.vy=0}
  p.y=player.rideY+bob*(player.jy>0?0:1)+player.jy;
  for(let i=0;i<AV.wheels.length;i++)AV.wheels[i].rotation.x+=player.v*dt*1.9;
  for(let i=0;i<AV.spin.length;i++)AV.spin[i].rotation.y+=dt*(8+Math.abs(player.v)*1.5);
  if(AV.petRoot){const pr=AV.petRoot,tx=p.x+Math.sin(player.heading)*2.4+Math.cos(player.heading)*1.6,tz=p.z+Math.cos(player.heading)*2.4-Math.sin(player.heading)*1.6;
    pr.position.x+=(tx-pr.position.x)*Math.min(1,dt*4);pr.position.z+=(tz-pr.position.z)*Math.min(1,dt*4);
    pr.position.y=Math.abs(Math.sin(time*9))*(.18+.2*sp);pr.rotation.y=Math.atan2(p.x-pr.position.x,p.z-pr.position.z)+Math.PI}
  dir.position.set(p.x-24,48,p.z-26);dir.target.position.set(p.x,0,p.z);
  const fov=55+Math.max(0,Math.abs(player.v)/6.4-1)*7;if(Math.abs(camera.fov-fov)>.05){camera.fov+=(fov-camera.fov)*Math.min(1,dt*4);camera.updateProjectionMatrix()}
  if(inShop){const h=player.heading,w=innerWidth<760;
    tp.set(p.x-Math.sin(h)*6.6+Math.cos(h)*1.4,2.7,p.z-Math.cos(h)*6.6-Math.sin(h)*1.4);
    tl.set(p.x+(w?0:-Math.cos(h)*2.7),w?.5:1.7,p.z+(w?0:Math.sin(h)*2.7));
  }else if(camState.follow){const back=9.5+(player.speedMul-1)*1.5;fwd.set(-Math.sin(player.heading),0,-Math.cos(player.heading));tp.set(p.x-fwd.x*back,5.6,p.z-fwd.z*back);tl.set(p.x+fwd.x*6,2.2,p.z+fwd.z*6)}
  else{state.orbit+=dt*.12;const a=state.orbit;tp.set(Math.sin(a)*16,6.5+Math.sin(a*.7)*1.5,24+Math.cos(a)*6);tl.set(0,4,-26)}
  const k=1-Math.exp(-dt*(inShop?3.2:camState.follow?4.5:1.6));camState.pos.lerp(tp,k);camState.look.lerp(tl,k);camera.position.copy(camState.pos);camera.lookAt(camState.look);
  fly.mat.uniforms.uTime.value=time;clouds.rotation.y+=dt*.002;
  for(let i=0;i<floaters.length;i++){const f=floaters[i];f.position.y=f.userData.y+Math.sin(time*.5+f.userData.ph)*1.2}
  for(let i=0;i<items.length;i++){const it=items[i];
    if(it.type==='info'){it.crystal.rotation.y+=dt*1.1;it.crystal.position.y=3.3+Math.sin(time*1.6+it.zi)*.25;it.r1.rotation.x=time*.8;it.r1.rotation.y=time*.5;it.r2.rotation.x=-time*.6;it.r2.rotation.z=time*.7}
    else if(it.type==='gate'){it.bm.uniforms.uTime.value=time;if(it.done&&it.open<1){it.open=Math.min(1,it.open+dt*.8);it.bm.uniforms.uOpen.value=it.open}}
    else{it.pm2.uniforms.uTime.value=time;it.portal.rotation.z=time*.3}}
  for(let i=0;i<coins.length;i++){const c=coins[i];c.rotation.y=time*2.2+i;c.position.y=1.5+Math.sin(time*2+i)*.2}
  if(frameNo%8===0){const cp=camera.position;for(const it of items){const d=Math.hypot(cp.x-it.pos.x,cp.z-it.pos.z),vis=d<200;it.group.visible=vis;it.bb.visible=vis}}
  for(let i=0;i<billboards.length;i++){const b=billboards[i];b.rotation.y=Math.atan2(camera.position.x-b.position.x,camera.position.z-b.position.z)}
  updBursts(dt);
  if(state.mode==='play'&&frameNo%2===0)drawMini();
  adapt(dt);
}
function frame(){
  if(dead)return;
  const dt=Math.min(.05,clock.getDelta());update(dt);
  if(Q.tier==='high'&&composer)composer.render();else renderer.render(scene,camera);
  raf=requestAnimationFrame(frame);
}
resize();applyLook(look);buildWorld('java');buildStepper();placePlayer(14);fmtPts();
const welcome=()=>{if(dead)return;if(save.welcome){toast('Welcome bonus: 150 points to spend in the shop');save.welcome=false;persist()}};
if(opts.store){opts.store.load().then(r=>{if(dead||!r)return;const mine=save.rev||0;
  if((r.rev||0)>mine&&Array.isArray(r.owned)){save.wallet=r.wallet|0;save.life=r.life|0;save.owned=r.owned;save.look=Object.assign({},DEFAULT_LOOK,r.look||{});save.rev=r.rev;save.welcome=false;look=Object.assign({},save.look);try{localStorage.setItem(SAVE_KEY,JSON.stringify(save))}catch(e){}applyLook(look);fmtPts()}
  else if(mine>(r.rev||0))pushRemote()}).catch(()=>{}).then(welcome)}else welcome();
(document.fonts&&document.fonts.load?Promise.all([document.fonts.load('700 40px "Chakra Petch"'),document.fonts.load('400 16px Figtree')]).catch(()=>{}):Promise.resolve()).then(()=>{if(dead)return;buildWorld('java');frame()});
const bExit=$('#bExit'),tExit=$('#tExit');
if(opts.onExit){bExit.hidden=false;tExit.hidden=false;bExit.addEventListener('click',()=>opts.onExit());tExit.addEventListener('click',()=>opts.onExit())}
const firstExtra=Object.keys(extra)[0];if(firstExtra)$('#q').value=WORLDS[firstExtra].title;
function dispose(){
  dead=true;buildToken++;if(remoteT)pushRemote();cancelAnimationFrame(raf);offs.forEach(f=>f());clearTimeout(toast.t);
  try{disposeGroup(world);scene.traverse(o=>{if(o.geometry)o.geometry.dispose();if(o.material)(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>{if(m.map)m.map.dispose();m.dispose()})});
  if(composer&&composer.dispose)composer.dispose();renderer.dispose();renderer.forceContextLoss()}catch(e){}
}
return dispose;
}
