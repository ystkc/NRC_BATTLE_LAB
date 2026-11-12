/** 用已安装 Playwright 的 Babel 解析器补齐前端函数与独立控制分支。 */
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../../../../..');
const {babelParse}=require(path.join(root,'node_modules/playwright/lib/transform/babelBundle.js'));
const rows=[];
function add(id,kind,name,source,node,parent,description){rows.push({item_id:id,kind,name,owner:'T12',source,line:node.loc.start.line,parent_id:parent,description,reachability:'独立前端分支，按 coverage 单列'});}
for(const filename of fs.readdirSync(path.join(root,'nrc_server/static')).filter(x=>x.endsWith('.js'))){
 const source='nrc_server/static/'+filename,text=fs.readFileSync(path.join(root,source),'utf8'),ast=babelParse(text,filename,true);
 function walk(node,parent='FILE:'+source,scope='module'){
  if(!node||typeof node!=='object'||!node.type)return;
  const key=filename+':'+node.loc.start.line+':'+node.loc.start.column+'-'+node.loc.end.line+':'+node.loc.end.column+':'+node.type;
  const fragment=n=>n?text.slice(n.start,n.end).replace(/\s+/g,' ').slice(0,240):'';
  if(['FunctionDeclaration','FunctionExpression','ArrowFunctionExpression'].includes(node.type)){
   const name=node.id?.name||scope+' callback';const id='JSFUNC:'+key;
   add(id,'js_function',name,source,node,parent,fragment(node).slice(0,160));parent=id;scope=name;
  }
  let desc,branches;
  if(node.type==='IfStatement'){desc='if '+fragment(node.test);branches=['true','false'];}
  if(node.type==='ConditionalExpression'){desc='ternary '+fragment(node.test);branches=['true','false'];}
  if(node.type==='LogicalExpression'){desc='logical '+node.operator+' '+fragment(node.left);branches=['rhs','short_circuit'];}
  if(['ForStatement','ForOfStatement','ForInStatement','WhileStatement','DoWhileStatement'].includes(node.type)){desc=node.type+' '+fragment(node.test||node.right);branches=['body','zero_or_exit'];}
  if(node.type==='CatchClause'){desc='catch '+fragment(node.param);branches=['exception'];}
  if(node.type==='SwitchCase'){desc='case '+fragment(node.test);branches=['case'];}
  if(branches)for(const branch of branches)add('JSBRANCH:'+key+':'+branch,'js_branch',scope+' / '+branch,source,node,parent,desc);
  for(const [key,value]of Object.entries(node)){if(['loc','start','end','extra','comments','tokens'].includes(key))continue;if(Array.isArray(value))for(const item of value)walk(item,parent,scope);else if(value&&typeof value==='object')walk(value,parent,scope);}
 }
 walk(ast.program);
}
const columns=['item_id','kind','name','owner','source','line','parent_id','description','reachability'];const quote=x=>'"'+String(x??'').replaceAll('"','""')+'"';
fs.writeFileSync(path.join(__dirname,'inventory_extra.csv'),columns.join(',')+'\n'+rows.map(r=>columns.map(c=>quote(r[c])).join(',')).join('\n')+'\n');
fs.writeFileSync(path.join(__dirname,'js_ast.json'),JSON.stringify(rows,null,2));console.log(JSON.stringify({objects:rows.length,functions:rows.filter(x=>x.kind==='js_function').length,branches:rows.filter(x=>x.kind==='js_branch').length}));
