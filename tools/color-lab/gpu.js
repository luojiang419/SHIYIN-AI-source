// 两张纹理常驻 WebGL，滑块只更新 uniform；无逐帧图片编码或网络请求。
class ColorGPU {
 constructor(canvas){
 this.canvas=canvas;const gl=this.gl=canvas.getContext('webgl',{alpha:false,preserveDrawingBuffer:true});if(!gl)throw Error('WebGL 不可用');
 const vertex='attribute vec2 p;varying vec2 uv;void main(){uv=(p+1.0)*0.5;gl_Position=vec4(p,0.,1.);}';
 const fragment=`precision highp float;
 varying vec2 uv;uniform sampler2D original;uniform sampler2D fitted;uniform vec4 area;uniform vec4 controls;uniform vec3 extra;
 float lin(float x){return x<=.04045?x/12.92:pow((x+.055)/1.055,2.4);}
 float enc(float x){return x<=.0031308?12.92*x:1.055*pow(max(x,0.),1./2.4)-.055;}
 float f(float x){return x>.008856?pow(x,1./3.):7.787*x+16./116.;}
 float inv(float x){return x>.206893?x*x*x:(x-16./116.)/7.787;}
 vec3 lab(vec3 c){c=vec3(lin(c.r),lin(c.g),lin(c.b));vec3 xyz=mat3(.4124564,.2126729,.0193339,.3575761,.7151522,.119192,.1804375,.072175,.9503041)*c;xyz/=vec3(.95047,1.,1.08883);xyz=vec3(f(xyz.x),f(xyz.y),f(xyz.z));return vec3(116.*xyz.y-16.,500.*(xyz.x-xyz.y),200.*(xyz.y-xyz.z));}
 vec3 rgb(vec3 c){float y=(c.x+16.)/116.;vec3 xyz=vec3(inv(y+c.y/500.),inv(y),inv(y-c.z/200.))*vec3(.95047,1.,1.08883);vec3 v=mat3(3.2404542,-.969266,.0556434,-1.5371385,1.8760108,-.2040259,-.4985314,.041556,1.0572252)*xyz;return clamp(vec3(enc(v.r),enc(v.g),enc(v.b)),0.,1.);}
 void main(){vec2 t=vec2(uv.x,1.-uv.y);vec3 src=texture2D(original,t).rgb;vec3 outc=src;if(t.x>=area.x&&t.y>=area.y&&t.x<area.z&&t.y<area.w){vec3 l=mix(lab(src),lab(texture2D(fitted,t).rgb),controls.x);l.x=(l.x-50.)*controls.z+50.+controls.y;l.yz=l.yz*controls.w+extra.xy;outc=rgb(l);}gl_FragColor=vec4(outc,1.);}`;
 const shader=(type,src)=>{const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s};
 this.program=gl.createProgram();gl.attachShader(this.program,shader(gl.VERTEX_SHADER,vertex));gl.attachShader(this.program,shader(gl.FRAGMENT_SHADER,fragment));gl.linkProgram(this.program);if(!gl.getProgramParameter(this.program,gl.LINK_STATUS))throw Error('着色器链接失败');gl.useProgram(this.program);
 const b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);const loc=gl.getAttribLocation(this.program,'p');gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,2,gl.FLOAT,false,0,0);
 this.textures=[0,1].map(i=>{gl.activeTexture(gl.TEXTURE0+i);const t=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,t);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gl.uniform1i(gl.getUniformLocation(this.program,i?'fitted':'original'),i);return t});this.frames=0;
 }
 upload(img,base){const gl=this.gl;this.canvas.width=img.width;this.canvas.height=img.height;gl.viewport(0,0,img.width,img.height);[img,base].forEach((im,i)=>{gl.activeTexture(gl.TEXTURE0+i);gl.bindTexture(gl.TEXTURE_2D,this.textures[i]);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGB,gl.RGB,gl.UNSIGNED_BYTE,im)});this.ready=true;}
 draw(c,box){if(!this.ready)return;const gl=this.gl,w=this.canvas.width,h=this.canvas.height;gl.useProgram(this.program);gl.uniform4f(gl.getUniformLocation(this.program,'area'),box[0]/w,box[1]/h,(box[0]+box[2])/w,(box[1]+box[3])/h);gl.uniform4f(gl.getUniformLocation(this.program,'controls'),c.model==='manual'?0:c.strength,c.lightness,c.contrast,c.chroma);gl.uniform3f(gl.getUniformLocation(this.program,'extra'),c.a_shift,c.b_shift,0);gl.drawArrays(gl.TRIANGLE_STRIP,0,4);this.frames++;}
}
window.ColorGPU=ColorGPU;
