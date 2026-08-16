(function(){const t=document.createElement("link").relList;if(t&&t.supports&&t.supports("modulepreload"))return;for(const r of document.querySelectorAll('link[rel="modulepreload"]'))i(r);new MutationObserver(r=>{for(const a of r)if(a.type==="childList")for(const n of a.addedNodes)n.tagName==="LINK"&&n.rel==="modulepreload"&&i(n)}).observe(document,{childList:!0,subtree:!0});function s(r){const a={};return r.integrity&&(a.integrity=r.integrity),r.referrerPolicy&&(a.referrerPolicy=r.referrerPolicy),r.crossOrigin==="use-credentials"?a.credentials="include":r.crossOrigin==="anonymous"?a.credentials="omit":a.credentials="same-origin",a}function i(r){if(r.ep)return;r.ep=!0;const a=s(r);fetch(r.href,a)}})();const J=globalThis,et=J.ShadowRoot&&(J.ShadyCSS===void 0||J.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,st=Symbol(),lt=new WeakMap;let gt=class{constructor(t,s,i){if(this._$cssResult$=!0,i!==st)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=s}get styleSheet(){let t=this.o;const s=this.t;if(et&&t===void 0){const i=s!==void 0&&s.length===1;i&&(t=lt.get(s)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),i&&lt.set(s,t))}return t}toString(){return this.cssText}};const xt=e=>new gt(typeof e=="string"?e:e+"",void 0,st),it=(e,...t)=>{const s=e.length===1?e[0]:t.reduce((i,r,a)=>i+(n=>{if(n._$cssResult$===!0)return n.cssText;if(typeof n=="number")return n;throw Error("Value passed to 'css' function must be a 'css' function result: "+n+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(r)+e[a+1],e[0]);return new gt(s,e,st)},At=(e,t)=>{if(et)e.adoptedStyleSheets=t.map(s=>s instanceof CSSStyleSheet?s:s.styleSheet);else for(const s of t){const i=document.createElement("style"),r=J.litNonce;r!==void 0&&i.setAttribute("nonce",r),i.textContent=s.cssText,e.appendChild(i)}},dt=et?e=>e:e=>e instanceof CSSStyleSheet?(t=>{let s="";for(const i of t.cssRules)s+=i.cssText;return xt(s)})(e):e;const{is:St,defineProperty:Ct,getOwnPropertyDescriptor:Et,getOwnPropertyNames:Pt,getOwnPropertySymbols:Ot,getPrototypeOf:Tt}=Object,Q=globalThis,ct=Q.trustedTypes,Ut=ct?ct.emptyScript:"",Rt=Q.reactiveElementPolyfillSupport,j=(e,t)=>e,Z={toAttribute(e,t){switch(t){case Boolean:e=e?Ut:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let s=e;switch(t){case Boolean:s=e!==null;break;case Number:s=e===null?null:Number(e);break;case Object:case Array:try{s=JSON.parse(e)}catch{s=null}}return s}},rt=(e,t)=>!St(e,t),pt={attribute:!0,type:String,converter:Z,reflect:!1,useDefault:!1,hasChanged:rt};Symbol.metadata??=Symbol("metadata"),Q.litPropertyMetadata??=new WeakMap;let R=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,s=pt){if(s.state&&(s.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((s=Object.create(s)).wrapped=!0),this.elementProperties.set(t,s),!s.noAccessor){const i=Symbol(),r=this.getPropertyDescriptor(t,i,s);r!==void 0&&Ct(this.prototype,t,r)}}static getPropertyDescriptor(t,s,i){const{get:r,set:a}=Et(this.prototype,t)??{get(){return this[s]},set(n){this[s]=n}};return{get:r,set(n){const c=r?.call(this);a?.call(this,n),this.requestUpdate(t,c,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??pt}static _$Ei(){if(this.hasOwnProperty(j("elementProperties")))return;const t=Tt(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(j("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(j("properties"))){const s=this.properties,i=[...Pt(s),...Ot(s)];for(const r of i)this.createProperty(r,s[r])}const t=this[Symbol.metadata];if(t!==null){const s=litPropertyMetadata.get(t);if(s!==void 0)for(const[i,r]of s)this.elementProperties.set(i,r)}this._$Eh=new Map;for(const[s,i]of this.elementProperties){const r=this._$Eu(s,i);r!==void 0&&this._$Eh.set(r,s)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){const s=[];if(Array.isArray(t)){const i=new Set(t.flat(1/0).reverse());for(const r of i)s.unshift(dt(r))}else t!==void 0&&s.push(dt(t));return s}static _$Eu(t,s){const i=s.attribute;return i===!1?void 0:typeof i=="string"?i:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){const t=new Map,s=this.constructor.elementProperties;for(const i of s.keys())this.hasOwnProperty(i)&&(t.set(i,this[i]),delete this[i]);t.size>0&&(this._$Ep=t)}createRenderRoot(){const t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return At(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,s,i){this._$AK(t,i)}_$ET(t,s){const i=this.constructor.elementProperties.get(t),r=this.constructor._$Eu(t,i);if(r!==void 0&&i.reflect===!0){const a=(i.converter?.toAttribute!==void 0?i.converter:Z).toAttribute(s,i.type);this._$Em=t,a==null?this.removeAttribute(r):this.setAttribute(r,a),this._$Em=null}}_$AK(t,s){const i=this.constructor,r=i._$Eh.get(t);if(r!==void 0&&this._$Em!==r){const a=i.getPropertyOptions(r),n=typeof a.converter=="function"?{fromAttribute:a.converter}:a.converter?.fromAttribute!==void 0?a.converter:Z;this._$Em=r;const c=n.fromAttribute(s,a.type);this[r]=c??this._$Ej?.get(r)??c,this._$Em=null}}requestUpdate(t,s,i,r=!1,a){if(t!==void 0){const n=this.constructor;if(r===!1&&(a=this[t]),i??=n.getPropertyOptions(t),!((i.hasChanged??rt)(a,s)||i.useDefault&&i.reflect&&a===this._$Ej?.get(t)&&!this.hasAttribute(n._$Eu(t,i))))return;this.C(t,s,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,s,{useDefault:i,reflect:r,wrapped:a},n){i&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,n??s??this[t]),a!==!0||n!==void 0)||(this._$AL.has(t)||(this.hasUpdated||i||(s=void 0),this._$AL.set(t,s)),r===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(s){Promise.reject(s)}const t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[r,a]of this._$Ep)this[r]=a;this._$Ep=void 0}const i=this.constructor.elementProperties;if(i.size>0)for(const[r,a]of i){const{wrapped:n}=a,c=this[r];n!==!0||this._$AL.has(r)||c===void 0||this.C(r,void 0,a,c)}}let t=!1;const s=this._$AL;try{t=this.shouldUpdate(s),t?(this.willUpdate(s),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(s)):this._$EM()}catch(i){throw t=!1,this._$EM(),i}t&&this._$AE(s)}willUpdate(t){}_$AE(t){this._$EO?.forEach(s=>s.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(s=>this._$ET(s,this[s])),this._$EM()}updated(t){}firstUpdated(t){}};R.elementStyles=[],R.shadowRootOptions={mode:"open"},R[j("elementProperties")]=new Map,R[j("finalized")]=new Map,Rt?.({ReactiveElement:R}),(Q.reactiveElementVersions??=[]).push("2.1.2");const at=globalThis,ht=e=>e,Y=at.trustedTypes,ut=Y?Y.createPolicy("lit-html",{createHTML:e=>e}):void 0,yt="$lit$",S=`lit$${Math.random().toFixed(9).slice(2)}$`,_t="?"+S,Ht=`<${_t}>`,T=document,I=()=>T.createComment(""),q=e=>e===null||typeof e!="object"&&typeof e!="function",nt=Array.isArray,Dt=e=>nt(e)||typeof e?.[Symbol.iterator]=="function",tt=`[ 	
\f\r]`,z=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,mt=/-->/g,vt=/>/g,P=RegExp(`>|${tt}(?:([^\\s"'>=/]+)(${tt}*=${tt}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),bt=/'/g,ft=/"/g,wt=/^(?:script|style|textarea|title)$/i,Nt=e=>(t,...s)=>({_$litType$:e,strings:t,values:s}),o=Nt(1),H=Symbol.for("lit-noChange"),l=Symbol.for("lit-nothing"),$t=new WeakMap,O=T.createTreeWalker(T,129);function kt(e,t){if(!nt(e)||!e.hasOwnProperty("raw"))throw Error("invalid template strings array");return ut!==void 0?ut.createHTML(t):t}const Mt=(e,t)=>{const s=e.length-1,i=[];let r,a=t===2?"<svg>":t===3?"<math>":"",n=z;for(let c=0;c<s;c++){const d=e[c];let v,b,m=-1,_=0;for(;_<d.length&&(n.lastIndex=_,b=n.exec(d),b!==null);)_=n.lastIndex,n===z?b[1]==="!--"?n=mt:b[1]!==void 0?n=vt:b[2]!==void 0?(wt.test(b[2])&&(r=RegExp("</"+b[2],"g")),n=P):b[3]!==void 0&&(n=P):n===P?b[0]===">"?(n=r??z,m=-1):b[1]===void 0?m=-2:(m=n.lastIndex-b[2].length,v=b[1],n=b[3]===void 0?P:b[3]==='"'?ft:bt):n===ft||n===bt?n=P:n===mt||n===vt?n=z:(n=P,r=void 0);const A=n===P&&e[c+1].startsWith("/>")?" ":"";a+=n===z?d+Ht:m>=0?(i.push(v),d.slice(0,m)+yt+d.slice(m)+S+A):d+S+(m===-2?c:A)}return[kt(e,a+(e[s]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),i]};class V{constructor({strings:t,_$litType$:s},i){let r;this.parts=[];let a=0,n=0;const c=t.length-1,d=this.parts,[v,b]=Mt(t,s);if(this.el=V.createElement(v,i),O.currentNode=this.el.content,s===2||s===3){const m=this.el.content.firstChild;m.replaceWith(...m.childNodes)}for(;(r=O.nextNode())!==null&&d.length<c;){if(r.nodeType===1){if(r.hasAttributes())for(const m of r.getAttributeNames())if(m.endsWith(yt)){const _=b[n++],A=r.getAttribute(m).split(S),K=/([.?@])?(.*)/.exec(_);d.push({type:1,index:a,name:K[2],strings:A,ctor:K[1]==="."?zt:K[1]==="?"?jt:K[1]==="@"?It:X}),r.removeAttribute(m)}else m.startsWith(S)&&(d.push({type:6,index:a}),r.removeAttribute(m));if(wt.test(r.tagName)){const m=r.textContent.split(S),_=m.length-1;if(_>0){r.textContent=Y?Y.emptyScript:"";for(let A=0;A<_;A++)r.append(m[A],I()),O.nextNode(),d.push({type:2,index:++a});r.append(m[_],I())}}}else if(r.nodeType===8)if(r.data===_t)d.push({type:2,index:a});else{let m=-1;for(;(m=r.data.indexOf(S,m+1))!==-1;)d.push({type:7,index:a}),m+=S.length-1}a++}}static createElement(t,s){const i=T.createElement("template");return i.innerHTML=t,i}}function D(e,t,s=e,i){if(t===H)return t;let r=i!==void 0?s._$Co?.[i]:s._$Cl;const a=q(t)?void 0:t._$litDirective$;return r?.constructor!==a&&(r?._$AO?.(!1),a===void 0?r=void 0:(r=new a(e),r._$AT(e,s,i)),i!==void 0?(s._$Co??=[])[i]=r:s._$Cl=r),r!==void 0&&(t=D(e,r._$AS(e,t.values),r,i)),t}class Lt{constructor(t,s){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=s}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){const{el:{content:s},parts:i}=this._$AD,r=(t?.creationScope??T).importNode(s,!0);O.currentNode=r;let a=O.nextNode(),n=0,c=0,d=i[0];for(;d!==void 0;){if(n===d.index){let v;d.type===2?v=new B(a,a.nextSibling,this,t):d.type===1?v=new d.ctor(a,d.name,d.strings,this,t):d.type===6&&(v=new qt(a,this,t)),this._$AV.push(v),d=i[++c]}n!==d?.index&&(a=O.nextNode(),n++)}return O.currentNode=T,r}p(t){let s=0;for(const i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(t,i,s),s+=i.strings.length-2):i._$AI(t[s])),s++}}class B{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,s,i,r){this.type=2,this._$AH=l,this._$AN=void 0,this._$AA=t,this._$AB=s,this._$AM=i,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode;const s=this._$AM;return s!==void 0&&t?.nodeType===11&&(t=s.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,s=this){t=D(this,t,s),q(t)?t===l||t==null||t===""?(this._$AH!==l&&this._$AR(),this._$AH=l):t!==this._$AH&&t!==H&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):Dt(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==l&&q(this._$AH)?this._$AA.nextSibling.data=t:this.T(T.createTextNode(t)),this._$AH=t}$(t){const{values:s,_$litType$:i}=t,r=typeof i=="number"?this._$AC(t):(i.el===void 0&&(i.el=V.createElement(kt(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===r)this._$AH.p(s);else{const a=new Lt(r,this),n=a.u(this.options);a.p(s),this.T(n),this._$AH=a}}_$AC(t){let s=$t.get(t.strings);return s===void 0&&$t.set(t.strings,s=new V(t)),s}k(t){nt(this._$AH)||(this._$AH=[],this._$AR());const s=this._$AH;let i,r=0;for(const a of t)r===s.length?s.push(i=new B(this.O(I()),this.O(I()),this,this.options)):i=s[r],i._$AI(a),r++;r<s.length&&(this._$AR(i&&i._$AB.nextSibling,r),s.length=r)}_$AR(t=this._$AA.nextSibling,s){for(this._$AP?.(!1,!0,s);t!==this._$AB;){const i=ht(t).nextSibling;ht(t).remove(),t=i}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}}class X{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,s,i,r,a){this.type=1,this._$AH=l,this._$AN=void 0,this.element=t,this.name=s,this._$AM=r,this.options=a,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=l}_$AI(t,s=this,i,r){const a=this.strings;let n=!1;if(a===void 0)t=D(this,t,s,0),n=!q(t)||t!==this._$AH&&t!==H,n&&(this._$AH=t);else{const c=t;let d,v;for(t=a[0],d=0;d<a.length-1;d++)v=D(this,c[i+d],s,d),v===H&&(v=this._$AH[d]),n||=!q(v)||v!==this._$AH[d],v===l?t=l:t!==l&&(t+=(v??"")+a[d+1]),this._$AH[d]=v}n&&!r&&this.j(t)}j(t){t===l?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}}class zt extends X{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===l?void 0:t}}class jt extends X{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==l)}}class It extends X{constructor(t,s,i,r,a){super(t,s,i,r,a),this.type=5}_$AI(t,s=this){if((t=D(this,t,s,0)??l)===H)return;const i=this._$AH,r=t===l&&i!==l||t.capture!==i.capture||t.once!==i.once||t.passive!==i.passive,a=t!==l&&(i===l||r);r&&this.element.removeEventListener(this.name,this,i),a&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}}class qt{constructor(t,s,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=s,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){D(this,t)}}const Vt=at.litHtmlPolyfillSupport;Vt?.(V,B),(at.litHtmlVersions??=[]).push("3.3.3");const Bt=(e,t,s)=>{const i=s?.renderBefore??t;let r=i._$litPart$;if(r===void 0){const a=s?.renderBefore??null;i._$litPart$=r=new B(t.insertBefore(I(),a),a,void 0,s??{})}return r._$AI(e),r};const ot=globalThis;class w extends R{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){const s=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=Bt(s,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return H}}w._$litElement$=!0,w.finalized=!0,ot.litElementHydrateSupport?.({LitElement:w});const Ft=ot.litElementPolyfillSupport;Ft?.({LitElement:w});(ot.litElementVersions??=[]).push("4.2.2");const F=e=>(t,s)=>{s!==void 0?s.addInitializer(()=>{customElements.define(e,t)}):customElements.define(e,t)};const Wt={attribute:!0,type:String,converter:Z,reflect:!1,hasChanged:rt},Gt=(e=Wt,t,s)=>{const{kind:i,metadata:r}=s;let a=globalThis.litPropertyMetadata.get(r);if(a===void 0&&globalThis.litPropertyMetadata.set(r,a=new Map),i==="setter"&&((e=Object.create(e)).wrapped=!0),a.set(s.name,e),i==="accessor"){const{name:n}=s;return{set(c){const d=t.get.call(this);t.set.call(this,c),this.requestUpdate(n,d,e,!0,c)},init(c){return c!==void 0&&this.C(n,void 0,e,c),c}}}if(i==="setter"){const{name:n}=s;return function(c){const d=this[n];t.call(this,c),this.requestUpdate(n,d,e,!0,c)}}throw Error("Unsupported decorator location: "+i)};function N(e){return(t,s)=>typeof s=="object"?Gt(e,t,s):((i,r,a)=>{const n=r.hasOwnProperty(a);return r.constructor.createProperty(a,i),n?Object.getOwnPropertyDescriptor(r,a):void 0})(e,t,s)}function p(e){return N({...e,state:!0,attribute:!1})}class k extends Error{constructor(t,s,i,r){super(i),this.status=t,this.code=s,this.detail=r,this.name="ApiError"}}async function h(e,t="GET",s){const i=await fetch(e,{method:t,headers:{"Content-Type":"application/json"},body:s===void 0?void 0:JSON.stringify(s)}),r=await i.text();let a={};if(r)try{a=JSON.parse(r)}catch{a={error:r.slice(0,200)}}if(!i.ok)throw new k(i.status,String(a.code??"Error"),String(a.error??i.statusText),a.detail?String(a.detail):void 0);return a}const u={info:()=>h("api/info"),vault:{status:()=>h("api/vault"),setPassphrase:e=>h("api/vault/passphrase","POST",{passphrase:e}),change:(e,t)=>h("api/vault/passphrase","PUT",{current:e,new:t}),remove:e=>h("api/vault/passphrase","DELETE",{passphrase:e}),unlock:e=>h("api/vault/unlock","POST",{passphrase:e}),lock:()=>h("api/vault/lock","POST")},credentials:{list:()=>h("api/credentials"),create:e=>h("api/credentials","POST",e),remove:e=>h(`api/credentials/${e}`,"DELETE"),rotate:e=>h(`api/credentials/${e}/rotate`,"POST"),setTier:(e,t)=>h(`api/credentials/${e}/tier`,"PUT",{tier:t}),test:(e,t)=>h(`api/credentials/${e}/test`,"POST",{url:t})},repos:{list:()=>h("api/repos"),add:e=>h("api/repos","POST",e),patch:(e,t)=>h(`api/repos/${e}`,"PATCH",t),remove:(e,t=!1)=>h(`api/repos/${e}?force=${t?1:0}`,"DELETE"),refs:e=>h(`api/repos/${e}/refs`),releases:e=>h(`api/repos/${e}/releases`),refresh:e=>h(`api/repos/${e}/refresh`,"POST"),install:(e,t)=>h(`api/repos/${e}/install`,"POST",{ref:t}),uninstall:(e,t=!1)=>h(`api/repos/${e}/uninstall`,"POST",{force:t})},hosts:{scan:(e,t=22)=>h("api/hosts/scan","POST",{host:e,port:t}),trust:e=>h("api/hosts/trust","POST",{lines:e})},updates:{check:()=>h("api/updates/check","POST")},core:{restart:()=>h("api/core/restart","POST")}},W=it`
  :host {
    --psm-bg: var(--primary-background-color, #f5f5f5);
    --psm-card: var(--card-background-color, #ffffff);
    --psm-fg: var(--primary-text-color, #212121);
    --psm-muted: var(--secondary-text-color, #727272);
    --psm-line: var(--divider-color, #e0e0e0);
    --psm-accent: var(--primary-color, #03a9f4);
    --psm-ok: var(--success-color, #43a047);
    --psm-warn: var(--warning-color, #ffa726);
    --psm-bad: var(--error-color, #db4437);
    --psm-radius: 12px;
  }

  @media (prefers-color-scheme: dark) {
    :host {
      --psm-bg: var(--primary-background-color, #111418);
      --psm-card: var(--card-background-color, #1c1f26);
      --psm-fg: var(--primary-text-color, #e1e1e1);
      --psm-muted: var(--secondary-text-color, #9b9b9b);
      --psm-line: var(--divider-color, #2c313a);
    }
  }
`,G=it`
  * {
    box-sizing: border-box;
  }

  .card {
    background: var(--psm-card);
    border: 1px solid var(--psm-line);
    border-radius: var(--psm-radius);
    padding: 16px 20px;
    margin-bottom: 12px;
  }

  h2 {
    margin: 0 0 4px;
    font-size: 18px;
    font-weight: 600;
  }

  h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
  }

  p.hint {
    margin: 0 0 16px;
    color: var(--psm-muted);
    font-size: 13px;
  }

  button {
    font: inherit;
    font-size: 13px;
    padding: 7px 14px;
    border-radius: 8px;
    border: 1px solid var(--psm-line);
    background: transparent;
    color: var(--psm-fg);
    cursor: pointer;
    transition: background 120ms ease, border-color 120ms ease;
  }
  button:hover:not(:disabled) {
    border-color: var(--psm-accent);
  }
  button:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  button.primary {
    background: var(--psm-accent);
    border-color: var(--psm-accent);
    color: #fff;
  }
  button.danger {
    color: var(--psm-bad);
    border-color: color-mix(in srgb, var(--psm-bad) 40%, transparent);
  }
  button.danger:hover:not(:disabled) {
    border-color: var(--psm-bad);
  }

  input,
  select,
  textarea {
    font: inherit;
    font-size: 13px;
    width: 100%;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid var(--psm-line);
    background: var(--psm-bg);
    color: var(--psm-fg);
  }
  input:focus,
  select:focus,
  textarea:focus {
    outline: 2px solid color-mix(in srgb, var(--psm-accent) 45%, transparent);
    outline-offset: -1px;
  }
  textarea {
    min-height: 110px;
    font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
    resize: vertical;
  }

  label {
    display: block;
    margin-bottom: 12px;
    font-size: 12px;
    color: var(--psm-muted);
  }
  label > span {
    display: block;
    margin-bottom: 5px;
  }
  label.inline {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--psm-fg);
  }
  label.inline input {
    width: auto;
  }

  .row {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }
  .grow {
    flex: 1;
    min-width: 0;
  }
  .actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 12px;
  }
  .grid2 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0 16px;
  }

  .pill {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.02em;
    white-space: nowrap;
  }
  .pill.ok {
    background: color-mix(in srgb, var(--psm-ok) 18%, transparent);
    color: var(--psm-ok);
  }
  .pill.warn {
    background: color-mix(in srgb, var(--psm-warn) 20%, transparent);
    color: var(--psm-warn);
  }
  .pill.bad {
    background: color-mix(in srgb, var(--psm-bad) 18%, transparent);
    color: var(--psm-bad);
  }
  .pill.plain {
    background: color-mix(in srgb, var(--psm-muted) 16%, transparent);
    color: var(--psm-muted);
  }

  code,
  .mono {
    font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
    font-size: 12px;
    word-break: break-all;
  }

  .banner {
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 13px;
    margin-bottom: 12px;
  }
  .banner.bad {
    background: color-mix(in srgb, var(--psm-bad) 12%, transparent);
    color: var(--psm-bad);
  }
  .banner.ok {
    background: color-mix(in srgb, var(--psm-ok) 12%, transparent);
    color: var(--psm-ok);
  }
  .banner.warn {
    background: color-mix(in srgb, var(--psm-warn) 14%, transparent);
    color: var(--psm-warn);
  }

  .empty {
    text-align: center;
    color: var(--psm-muted);
    padding: 36px 12px;
    font-size: 14px;
  }

  dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 4px 14px;
    margin: 0;
    font-size: 13px;
  }
  dt {
    color: var(--psm-muted);
  }
  dd {
    margin: 0;
  }
`;var Kt=Object.defineProperty,Jt=Object.getOwnPropertyDescriptor,g=(e,t,s,i)=>{for(var r=i>1?void 0:i?Jt(t,s):t,a=e.length-1,n;a>=0;a--)(n=e[a])&&(r=(i?n(t,s,r):n(r))||r);return i&&r&&Kt(t,s,r),r};let f=class extends w{constructor(){super(...arguments),this.items=[],this.busy=!1,this.error="",this.notice="",this.adding=!1,this.kind="ssh",this.importing=!1,this.copied=""}connectedCallback(){super.connectedCallback(),this.load()}async load(){try{this.items=await u.credentials.list()}catch(e){this.error=e instanceof k?e.message:String(e)}}render(){return o`
      ${this.error?o`<div class="banner bad">${this.error}</div>`:l}
      ${this.notice?o`<div class="banner ok">${this.notice}</div>`:l}

      <div class="card">
        <div class="row">
          <div class="grow">
            <h2>Credentials</h2>
            <p class="hint" style="margin:0">
              One credential per repository keeps the blast radius of a leak to a single repository.
            </p>
          </div>
          <button class="primary" @click=${()=>this.adding=!this.adding}>
            ${this.adding?"Cancel":"Add credential"}
          </button>
        </div>
      </div>

      ${this.adding?this.renderForm():l}
      ${this.items.length===0&&!this.adding?o`<div class="card"><div class="empty">No credentials yet.</div></div>`:this.items.map(e=>this.renderCredential(e))}
    `}renderForm(){return o`
      <div class="card">
        <h3>New credential</h3>
        <div class="actions" style="margin:12px 0">
          <button class=${this.kind==="ssh"?"primary":""} @click=${()=>this.kind="ssh"}>
            SSH deploy key
          </button>
          <button
            class=${this.kind==="token"?"primary":""}
            @click=${()=>this.kind="token"}
          >
            Access token
          </button>
        </div>

        <form @submit=${this.onCreate}>
          <div class="grid2">
            <label>
              <span>Label</span>
              <input name="label" required placeholder="my-private-card" />
            </label>
            <label>
              <span>Tier</span>
              <select name="tier">
                <option value="unattended">unattended, updates without you</option>
                <option value="protected" ?disabled=${!this.status.passphrase_set}>
                  protected, needs the passphrase
                </option>
              </select>
            </label>
          </div>

          ${this.kind==="ssh"?this.renderSshFields():this.renderTokenFields()}

          <div class="actions">
            <button class="primary" ?disabled=${this.busy} type="submit">
              ${this.busy?"Working…":this.kind==="ssh"&&!this.importing?"Generate key":"Save"}
            </button>
          </div>
        </form>
      </div>
    `}renderSshFields(){return o`
      <label class="inline" style="margin-bottom:12px">
        <input
          type="checkbox"
          .checked=${this.importing}
          @change=${e=>this.importing=e.target.checked}
        />
        Paste an existing private key instead of generating one
      </label>
      ${this.importing?o`<label>
            <span>Private key, unencrypted OpenSSH or PEM</span>
            <textarea name="private_key" required placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"></textarea>
          </label>`:o`<p class="hint">
            A fresh Ed25519 key is generated. Copy the public half into the repository's deploy keys.
          </p>`}
    `}renderTokenFields(){return o`
      <div class="grid2">
        <label>
          <span>Token</span>
          <input name="token" type="password" required placeholder="github_pat_… or glpat-…" />
        </label>
        <label>
          <span>Username, optional</span>
          <input name="username" placeholder="x-access-token" />
        </label>
      </div>
    `}renderCredential(e){const t=e.tier==="protected"&&!this.status.unlocked;return o`
      <div class="card">
        <div class="row">
          <h3 class="grow">${e.label}</h3>
          <span class="pill plain">${e.kind}</span>
          <span class="pill ${e.tier==="protected"?"warn":"plain"}">${e.tier}</span>
          ${t?o`<span class="pill bad">locked</span>`:l}
        </div>

        <dl style="margin-top:10px">
          ${e.fingerprint?o`<dt>Fingerprint</dt>
                <dd class="mono">${e.fingerprint}</dd>`:l}
          ${e.username?o`<dt>Username</dt><dd>${e.username}</dd>`:l}
          <dt>Used by</dt>
          <dd>${e.repo_count} ${e.repo_count===1?"repository":"repositories"}</dd>
        </dl>

        ${e.public_key?o`
              <label style="margin-top:12px">
                <span>Public key, paste this into the deploy keys of the repository</span>
                <textarea readonly style="min-height:72px">${e.public_key}</textarea>
              </label>
              <button @click=${()=>this.copy(e)}>
                ${this.copied===e.id?"Copied":"Copy public key"}
              </button>
            `:l}

        <div class="actions">
          ${e.kind==="ssh"?o`<button ?disabled=${this.busy||t} @click=${()=>this.rotate(e)}>
                Rotate key
              </button>`:l}
          <button
            ?disabled=${this.busy||!this.status.passphrase_set||!this.status.unlocked}
            @click=${()=>this.move(e)}
            title=${this.status.passphrase_set?"":"Set a passphrase first"}
          >
            Move to ${e.tier==="protected"?"unattended":"protected"}
          </button>
          <button class="danger" ?disabled=${this.busy||e.repo_count>0} @click=${()=>this.deleteCredential(e)}>
            Delete
          </button>
        </div>
      </div>
    `}async copy(e){try{await navigator.clipboard.writeText(e.public_key??""),this.copied=e.id,setTimeout(()=>this.copied="",2e3)}catch{this.error="Clipboard access was refused, select the text manually"}}async act(e,t){this.busy=!0,this.error="",this.notice="";try{await e(),this.notice=t,await this.load(),this.dispatchEvent(new CustomEvent("credentials-changed",{bubbles:!0,composed:!0}))}catch(s){this.error=s instanceof k?s.message:String(s)}finally{this.busy=!1}}onCreate(e){e.preventDefault();const t=new FormData(e.target),s={kind:this.kind,label:String(t.get("label")??""),tier:String(t.get("tier")??"unattended")};if(this.kind==="ssh"&&this.importing&&(s.private_key=String(t.get("private_key")??"")),this.kind==="token"){s.token=String(t.get("token")??"");const i=String(t.get("username")??"").trim();i&&(s.username=i)}this.act(async()=>{await u.credentials.create(s),this.adding=!1},"Credential created")}rotate(e){this.act(()=>u.credentials.rotate(e.id),"New key generated, update the deploy key")}move(e){const t=e.tier==="protected"?"unattended":"protected";this.act(()=>u.credentials.setTier(e.id,t),`Moved to the ${t} tier`)}deleteCredential(e){this.act(()=>u.credentials.remove(e.id),"Credential deleted")}};f.styles=[W,G];g([N({attribute:!1})],f.prototype,"status",2);g([p()],f.prototype,"items",2);g([p()],f.prototype,"busy",2);g([p()],f.prototype,"error",2);g([p()],f.prototype,"notice",2);g([p()],f.prototype,"adding",2);g([p()],f.prototype,"kind",2);g([p()],f.prototype,"importing",2);g([p()],f.prototype,"copied",2);f=g([F("psm-credentials-view")],f);var Zt=Object.defineProperty,Yt=Object.getOwnPropertyDescriptor,y=(e,t,s,i)=>{for(var r=i>1?void 0:i?Yt(t,s):t,a=e.length-1,n;a>=0;a--)(n=e[a])&&(r=(i?n(t,s,r):n(r))||r);return i&&r&&Zt(t,s,r),r};const Qt=[["","detect automatically"],["integration","integration"],["plugin","Lovelace card"],["theme","theme"],["python_script","python script"],["appdaemon","AppDaemon app"],["addon","Home Assistant add-on"]];let $=class extends w{constructor(){super(...arguments),this.credentials=[],this.items=[],this.busy="",this.error="",this.notice="",this.adding=!1,this.expanded="",this.refs={}}connectedCallback(){super.connectedCallback(),this.load()}async load(){try{this.items=await u.repos.list()}catch(e){this.error=e instanceof k?e.message:String(e)}}render(){const e=this.items.filter(t=>t.update_available).length;return o`
      ${this.error?o`<div class="banner bad">${this.error}</div>`:l}
      ${this.notice?o`<div class="banner ok">${this.notice}</div>`:l}

      <div class="card">
        <div class="row">
          <div class="grow">
            <h2>Repositories</h2>
            <p class="hint" style="margin:0">
              ${this.items.length} tracked${e?`, ${e} with updates available`:""}
            </p>
          </div>
          <button ?disabled=${this.busy!==""} @click=${this.checkAll}>Check for updates</button>
          <button class="primary" @click=${()=>this.adding=!this.adding}>
            ${this.adding?"Cancel":"Add repository"}
          </button>
        </div>
      </div>

      ${this.adding?this.renderAdd():l}
      ${this.items.length===0&&!this.adding?o`<div class="card"><div class="empty">Nothing tracked yet.</div></div>`:this.items.map(t=>this.renderRepo(t))}
    `}renderAdd(){return o`
      <div class="card">
        <h3>Add repository</h3>
        <p class="hint">
          Any git URL. Use an ssh URL with a deploy key, or an https URL with a token.
        </p>
        <form @submit=${this.onAdd}>
          <label>
            <span>Repository URL</span>
            <input name="url" required placeholder="git@github.com:me/my-private-card.git" />
          </label>
          <div class="grid2">
            <label>
              <span>Credential</span>
              <select name="credential_id">
                <option value="">none, public repository</option>
                ${this.credentials.map(e=>o`<option value=${e.id}>${e.label} (${e.kind}, ${e.tier})</option>`)}
              </select>
            </label>
            <label>
              <span>Category</span>
              <select name="category">
                ${Qt.map(([e,t])=>o`<option value=${e}>${t}</option>`)}
              </select>
            </label>
            <label>
              <span>Track</span>
              <select name="ref_kind">
                <option value="tag">newest tag</option>
                <option value="branch">a branch</option>
              </select>
            </label>
            <label>
              <span>Pin to a specific ref, optional</span>
              <input name="pinned_ref" placeholder="v1.2.3 or main" />
            </label>
          </div>
          <label class="inline" style="margin-bottom:12px">
            <input type="checkbox" name="auto_update" />
            Install updates automatically
          </label>
          <div class="actions">
            <button class="primary" ?disabled=${this.busy!==""} type="submit">
              ${this.busy==="add"?"Cloning…":"Add"}
            </button>
          </div>
        </form>
      </div>
    `}renderRepo(e){const t=this.expanded===e.id,s=this.busy===e.id;return o`
      <div class="card">
        <div class="row">
          <div class="grow">
            <h3>${e.slug}</h3>
            <div class="hint" style="margin:2px 0 0">${e.host} · ${e.category}</div>
          </div>
          ${e.update_available?o`<span class="pill warn">update ${e.available_version}</span>`:l}
          <span class="pill ${e.installed?"ok":"plain"}">
            ${e.installed?e.installed_version??"installed":"not installed"}
          </span>
        </div>

        ${e.last_error?o`<div class="banner bad" style="margin-top:10px">${e.last_error}</div>`:l}

        <div class="actions">
          <button
            class=${e.update_available||!e.installed?"primary":""}
            ?disabled=${s}
            @click=${()=>this.install(e)}
          >
            ${s?"Working…":e.installed?"Update":"Install"}
          </button>
          <button ?disabled=${s} @click=${()=>this.refresh(e)}>Check</button>
          <button ?disabled=${s} @click=${()=>this.toggle(e)}>
            ${t?"Hide":"Details"}
          </button>
          ${e.installed?o`<button ?disabled=${s} @click=${()=>this.uninstall(e)}>Uninstall</button>`:l}
          <button class="danger" ?disabled=${s} @click=${()=>this.deleteRepo(e)}>Remove</button>
        </div>

        ${t?this.renderDetails(e):l}
      </div>
    `}renderDetails(e){const t=this.refs[e.id]??[];return o`
      <div style="margin-top:16px; border-top:1px solid var(--psm-line); padding-top:14px">
        <dl>
          <dt>URL</dt><dd class="mono">${e.url}</dd>
          <dt>Tracking</dt><dd>${e.pinned_ref?`pinned to ${e.pinned_ref}`:`newest ${e.ref_kind}`}</dd>
          <dt>Installed ref</dt><dd class="mono">${e.installed_ref?.slice(0,12)??"none"}</dd>
          <dt>Last checked</dt><dd>${e.last_checked??"never"}</dd>
        </dl>

        <div class="grid2" style="margin-top:14px">
          <label>
            <span>Credential</span>
            <select @change=${s=>this.patch(e,{credential_id:s.target.value})}>
              <option value="" ?selected=${!e.credential_id}>none</option>
              ${this.credentials.map(s=>o`<option value=${s.id} ?selected=${s.id===e.credential_id}>
                  ${s.label}
                </option>`)}
            </select>
          </label>
          <label>
            <span>Install a specific ref</span>
            <select @change=${s=>this.install(e,s.target.value)}>
              <option value="">choose a ref…</option>
              ${t.map(s=>o`<option value=${s.name}>${s.name} (${s.kind})</option>`)}
            </select>
          </label>
        </div>

        <label class="inline">
          <input
            type="checkbox"
            .checked=${e.auto_update}
            @change=${s=>this.patch(e,{auto_update:s.target.checked})}
          />
          Install updates automatically
        </label>
      </div>
    `}async act(e,t,s){this.busy=e,this.error="",this.notice="";try{await t(),this.notice=s,await this.load()}catch(i){this.error=i instanceof k?`${i.message}${i.detail?` — ${i.detail}`:""}`:String(i)}finally{this.busy=""}}onAdd(e){e.preventDefault();const t=new FormData(e.target),s={url:String(t.get("url")??"").trim(),credential_id:String(t.get("credential_id")??"")||null,category:String(t.get("category")??"")||null,ref_kind:String(t.get("ref_kind")??"tag"),pinned_ref:String(t.get("pinned_ref")??"").trim()||null,auto_update:t.get("auto_update")==="on"};this.act("add",async()=>{await u.repos.add(s),this.adding=!1},"Repository added")}install(e,t){t!==""&&this.act(e.id,()=>u.repos.install(e.id,t),`Installed ${e.slug}`)}refresh(e){this.act(e.id,()=>u.repos.refresh(e.id),`Checked ${e.slug}`)}uninstall(e){this.act(e.id,async()=>{const t=await u.repos.uninstall(e.id);if(t.modified.length)throw new k(409,"Modified",`Locally modified files were left alone: ${t.modified.join(", ")}`)},`Uninstalled ${e.slug}`)}deleteRepo(e){this.act(e.id,()=>u.repos.remove(e.id),`Removed ${e.slug}`)}patch(e,t){this.act(e.id,()=>u.repos.patch(e.id,t),"Saved")}async toggle(e){if(this.expanded===e.id){this.expanded="";return}if(this.expanded=e.id,!this.refs[e.id])try{this.refs={...this.refs,[e.id]:await u.repos.refs(e.id)}}catch{this.refs={...this.refs,[e.id]:[]}}}checkAll(){this.act("all",async()=>{const e=await u.updates.check();this.notice=`Checked ${e.checked}, ${e.updates.length} with updates${e.skipped_locked?`, ${e.skipped_locked} skipped while locked`:""}`},"")}};$.styles=[W,G];y([N({attribute:!1})],$.prototype,"status",2);y([N({attribute:!1})],$.prototype,"credentials",2);y([p()],$.prototype,"items",2);y([p()],$.prototype,"busy",2);y([p()],$.prototype,"error",2);y([p()],$.prototype,"notice",2);y([p()],$.prototype,"adding",2);y([p()],$.prototype,"expanded",2);y([p()],$.prototype,"refs",2);$=y([F("psm-repos-view")],$);var Xt=Object.defineProperty,te=Object.getOwnPropertyDescriptor,U=(e,t,s,i)=>{for(var r=i>1?void 0:i?te(t,s):t,a=e.length-1,n;a>=0;a--)(n=e[a])&&(r=(i?n(t,s,r):n(r))||r);return i&&r&&Xt(t,s,r),r};let x=class extends w{constructor(){super(...arguments),this.busy=!1,this.error="",this.notice="",this.scanned=[],this.scannedHost=""}render(){return o`
      ${this.error?o`<div class="banner bad">${this.error}</div>`:l}
      ${this.notice?o`<div class="banner ok">${this.notice}</div>`:l}

      <div class="card">
        <h2>Trust a git host</h2>
        <p class="hint">
          GitHub and GitLab are trusted out of the box. Any other ssh host has to be confirmed
          once. Check the fingerprint against what the server operator publishes before accepting.
        </p>
        <form @submit=${this.onScan}>
          <div class="grid2">
            <label><span>Host</span><input name="host" required placeholder="gitea.lan" /></label>
            <label><span>Port</span><input name="port" type="number" value="22" /></label>
          </div>
          <div class="actions">
            <button class="primary" ?disabled=${this.busy} type="submit">Scan</button>
          </div>
        </form>

        ${this.scanned.length?o`
              <div style="margin-top:16px">
                <h3>${this.scannedHost} offered these keys</h3>
                <dl style="margin-top:10px">
                  ${this.scanned.map(e=>o`<dt>${e.type}</dt>
                      <dd class="mono">${e.fingerprint}</dd>`)}
                </dl>
                <div class="actions">
                  <button class="primary" ?disabled=${this.busy} @click=${this.onTrust}>
                    Trust these keys
                  </button>
                  <button @click=${()=>this.scanned=[]}>Discard</button>
                </div>
              </div>
            `:l}
      </div>

      <div class="card">
        <h2>Home Assistant</h2>
        <p class="hint">
          Newly installed integrations only load after a restart. Lovelace cards and themes do not
          need one.
        </p>
        <div class="actions">
          <button
            class="danger"
            ?disabled=${this.busy||!this.info?.supervisor}
            @click=${this.onRestart}
          >
            Restart Home Assistant
          </button>
        </div>
        ${this.info?.supervisor?l:o`<div class="banner warn" style="margin-top:12px">
              No Supervisor connection, so Core actions are unavailable. This is expected when
              running outside Home Assistant.
            </div>`}
      </div>

      <div class="card">
        <h2>About</h2>
        <dl style="margin-top:10px">
          <dt>Version</dt>
          <dd>${this.info?.version??"unknown"}</dd>
          <dt>Supervisor</dt>
          <dd>${this.info?.supervisor?"connected":"not available"}</dd>
          ${this.info?.dev_mode?o`<dt>Mode</dt><dd>development</dd>`:l}
        </dl>
      </div>
    `}async run(e){this.busy=!0,this.error="",this.notice="";try{await e()}catch(t){this.error=t instanceof k?t.message:String(t)}finally{this.busy=!1}}onScan(e){e.preventDefault();const t=new FormData(e.target),s=String(t.get("host")??"").trim(),i=Number(t.get("port")??22);this.run(async()=>{const r=await u.hosts.scan(s,i);this.scanned=r.keys,this.scannedHost=`${r.host}:${r.port}`})}onTrust(){this.run(async()=>{const e=await u.hosts.trust(this.scanned.map(t=>t.line));this.notice=`Added ${e.added} host ${e.added===1?"key":"keys"}`,this.scanned=[]})}onRestart(){this.run(async()=>{await u.core.restart(),this.notice="Restart requested. Home Assistant will be unreachable for a moment."})}};x.styles=[W,G];U([N({attribute:!1})],x.prototype,"info",2);U([p()],x.prototype,"busy",2);U([p()],x.prototype,"error",2);U([p()],x.prototype,"notice",2);U([p()],x.prototype,"scanned",2);U([p()],x.prototype,"scannedHost",2);x=U([F("psm-settings-view")],x);var ee=Object.defineProperty,se=Object.getOwnPropertyDescriptor,M=(e,t,s,i)=>{for(var r=i>1?void 0:i?se(t,s):t,a=e.length-1,n;a>=0;a--)(n=e[a])&&(r=(i?n(t,s,r):n(r))||r);return i&&r&&ee(t,s,r),r};let C=class extends w{constructor(){super(...arguments),this.busy=!1,this.error="",this.notice="",this.mode="none"}render(){return o`
      ${this.error?o`<div class="banner bad">${this.error}</div>`:l}
      ${this.notice?o`<div class="banner ok">${this.notice}</div>`:l}
      ${this.status.passphrase_set?this.renderConfigured():this.renderSetup()}
      ${this.renderExplainer()}
    `}renderSetup(){return o`
      <div class="card">
        <h2>Set a passphrase</h2>
        <p class="hint">
          Optional. Credentials in the protected tier are encrypted with this passphrase, which is
          never written to disk. The vault locks on every add-on restart until you re-enter it.
        </p>
        <form @submit=${this.onCreate}>
          <label>
            <span>Passphrase, at least 10 characters</span>
            <input name="passphrase" type="password" autocomplete="new-password" required />
          </label>
          <label>
            <span>Confirm</span>
            <input name="confirm" type="password" autocomplete="new-password" required />
          </label>
          <div class="actions">
            <button class="primary" ?disabled=${this.busy} type="submit">
              ${this.busy?"Calibrating…":"Set passphrase"}
            </button>
          </div>
        </form>
      </div>
    `}renderConfigured(){const{unlocked:e,retry_after:t,failed_attempts:s,kdf_n:i}=this.status;return o`
      <div class="card">
        <div class="row">
          <h2 class="grow">Vault</h2>
          <span class="pill ${e?"ok":"warn"}">${e?"unlocked":"locked"}</span>
        </div>
        <p class="hint">
          ${e?"Protected credentials are available until the add-on restarts.":"Protected repositories cannot be reached until you unlock."}
        </p>

        ${e?this.renderUnlocked():this.renderUnlock(t,s)}

        <dl style="margin-top:16px">
          <dt>Key derivation</dt>
          <dd>scrypt, cost ${i??"unknown"}</dd>
          <dt>Auto lock</dt>
          <dd>
            ${this.status.auto_lock_minutes>0?`after ${this.status.auto_lock_minutes} idle minutes`:"disabled"}
          </dd>
        </dl>
      </div>
      ${this.mode==="change"?this.renderChange():l}
      ${this.mode==="remove"?this.renderRemove():l}
    `}renderUnlock(e,t){return o`
      <form @submit=${this.onUnlock}>
        <label>
          <span>Passphrase</span>
          <input name="passphrase" type="password" autocomplete="current-password" required />
        </label>
        ${e>0?o`<div class="banner warn">
              ${t} failed ${t===1?"attempt":"attempts"}. Wait
              ${Math.ceil(e)}s before trying again.
            </div>`:l}
        <div class="actions">
          <button class="primary" ?disabled=${this.busy||e>0} type="submit">Unlock</button>
        </div>
      </form>
    `}renderUnlocked(){return o`
      <div class="actions">
        <button @click=${this.onLock} ?disabled=${this.busy}>Lock now</button>
        <button @click=${()=>this.mode=this.mode==="change"?"none":"change"}>
          Change passphrase
        </button>
        <button class="danger" @click=${()=>this.mode=this.mode==="remove"?"none":"remove"}>
          Remove passphrase
        </button>
      </div>
    `}renderChange(){return o`
      <div class="card">
        <h3>Change passphrase</h3>
        <p class="hint">Secrets are re-wrapped, not re-encrypted, so this is quick.</p>
        <form @submit=${this.onChange}>
          <label><span>Current</span><input name="current" type="password" required /></label>
          <label><span>New</span><input name="next" type="password" required /></label>
          <div class="actions">
            <button class="primary" ?disabled=${this.busy} type="submit">Change</button>
            <button type="button" @click=${()=>this.mode="none"}>Cancel</button>
          </div>
        </form>
      </div>
    `}renderRemove(){return o`
      <div class="card">
        <h3>Remove passphrase</h3>
        <div class="banner warn">
          Every protected credential moves down to the unattended tier, where it is protected only
          by a key file on disk. Background updates will keep working after a reboot.
        </div>
        <form @submit=${this.onRemove}>
          <label><span>Confirm with your passphrase</span><input name="passphrase" type="password" required /></label>
          <div class="actions">
            <button class="danger" ?disabled=${this.busy} type="submit">Remove passphrase</button>
            <button type="button" @click=${()=>this.mode="none"}>Cancel</button>
          </div>
        </form>
      </div>
    `}renderExplainer(){return o`
      <div class="card">
        <h3>What the two tiers mean</h3>
        <dl style="margin-top:10px">
          <dt><span class="pill plain">unattended</span></dt>
          <dd>
            Encrypted with a key file on disk, excluded from Home Assistant backups. Survives
            reboots so updates run without you. Does not protect against someone with root access.
          </dd>
          <dt style="margin-top:8px"><span class="pill plain">protected</span></dt>
          <dd>
            Encrypted with your passphrase. Protects against a stolen device or backup. Unavailable
            until unlocked, so these repositories are skipped by background checks while locked.
          </dd>
        </dl>
      </div>
    `}async run(e,t){this.busy=!0,this.error="",this.notice="";try{const s=await e();this.notice=t,this.mode="none",this.dispatchEvent(new CustomEvent("vault-changed",{detail:s,bubbles:!0,composed:!0}))}catch(s){this.error=s instanceof k?s.message:String(s),this.dispatchEvent(new CustomEvent("vault-refresh",{bubbles:!0,composed:!0}))}finally{this.busy=!1}}onCreate(e){e.preventDefault();const t=e.target,s=new FormData(t),i=String(s.get("passphrase")??"");if(i!==String(s.get("confirm")??"")){this.error="The two passphrases do not match";return}this.run(()=>u.vault.setPassphrase(i),"Passphrase set, vault unlocked")}onUnlock(e){e.preventDefault();const t=new FormData(e.target);this.run(()=>u.vault.unlock(String(t.get("passphrase")??"")),"Vault unlocked")}onLock(){this.run(()=>u.vault.lock(),"Vault locked")}onChange(e){e.preventDefault();const t=new FormData(e.target);this.run(()=>u.vault.change(String(t.get("current")??""),String(t.get("next")??"")),"Passphrase changed")}onRemove(e){e.preventDefault();const t=new FormData(e.target);this.run(()=>u.vault.remove(String(t.get("passphrase")??"")),"Passphrase removed")}};C.styles=[W,G];M([N({attribute:!1})],C.prototype,"status",2);M([p()],C.prototype,"busy",2);M([p()],C.prototype,"error",2);M([p()],C.prototype,"notice",2);M([p()],C.prototype,"mode",2);C=M([F("psm-vault-view")],C);var ie=Object.defineProperty,re=Object.getOwnPropertyDescriptor,L=(e,t,s,i)=>{for(var r=i>1?void 0:i?re(t,s):t,a=e.length-1,n;a>=0;a--)(n=e[a])&&(r=(i?n(t,s,r):n(r))||r);return i&&r&&ie(t,s,r),r};const ae=[["repos","Repositories"],["credentials","Credentials"],["vault","Vault"],["settings","Settings"]],ne=it`
  :host {
    display: block;
    min-height: 100vh;
    background: var(--psm-bg);
    color: var(--psm-fg);
    font: 14px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  .page {
    max-width: 940px;
    margin: 0 auto;
    padding: 20px 16px 48px;
  }
  h1 {
    margin: 0 0 14px;
    font-size: 22px;
    font-weight: 600;
  }
  nav {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
    border-bottom: 1px solid var(--psm-line);
    margin-bottom: 16px;
  }
  button.tab {
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    padding: 9px 14px;
    color: var(--psm-muted);
    display: inline-flex;
    align-items: center;
    gap: 7px;
  }
  button.tab:hover {
    color: var(--psm-fg);
  }
  button.tab.active {
    color: var(--psm-accent);
    border-bottom-color: var(--psm-accent);
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    display: inline-block;
  }
  .dot.ok {
    background: var(--psm-ok);
  }
  .dot.warn {
    background: var(--psm-warn);
  }
`;let E=class extends w{constructor(){super(...arguments),this.tab="repos",this.credentials=[],this.fatal=""}connectedCallback(){super.connectedCallback(),this.bootstrap(),this.addEventListener("vault-changed",e=>{this.status=e.detail,this.loadCredentials()}),this.addEventListener("vault-refresh",()=>{this.loadStatus()}),this.addEventListener("credentials-changed",()=>{this.loadCredentials()})}render(){if(this.fatal)return o`<div class="page"><div class="banner bad">${this.fatal}</div></div>`;if(!this.status)return o`<div class="page"><div class="empty">Loading…</div></div>`;const e=this.status.passphrase_set&&!this.status.unlocked;return o`
      <div class="page">
        <h1>Private Sources</h1>
        <nav>
          ${ae.map(([t,s])=>o`
              <button class="tab ${this.tab===t?"active":""}" @click=${()=>this.tab=t}>
                ${s}
                ${t==="vault"&&this.status?.passphrase_set?o`<span class="dot ${this.status.unlocked?"ok":"warn"}"></span>`:l}
              </button>
            `)}
        </nav>

        ${e&&this.tab!=="vault"?o`<div class="banner warn">
              The vault is locked. Protected repositories cannot be reached until you unlock it on
              the Vault tab.
            </div>`:l}

        <main>${this.renderTab()}</main>
      </div>
    `}renderTab(){const e=this.status;switch(this.tab){case"vault":return o`<psm-vault-view .status=${e}></psm-vault-view>`;case"credentials":return o`<psm-credentials-view .status=${e}></psm-credentials-view>`;case"settings":return o`<psm-settings-view .info=${this.info}></psm-settings-view>`;default:return o`<psm-repos-view
          .status=${e}
          .credentials=${this.credentials}
        ></psm-repos-view>`}}async bootstrap(){try{const[e,t]=await Promise.all([u.info(),u.vault.status()]);this.info=e,this.status=t,await this.loadCredentials()}catch(e){this.fatal=e instanceof k?e.message:String(e)}}async loadStatus(){try{this.status=await u.vault.status()}catch{}}async loadCredentials(){try{this.credentials=await u.credentials.list()}catch{this.credentials=[]}}};E.styles=[W,G,ne];L([p()],E.prototype,"tab",2);L([p()],E.prototype,"status",2);L([p()],E.prototype,"info",2);L([p()],E.prototype,"credentials",2);L([p()],E.prototype,"fatal",2);E=L([F("psm-app")],E);
