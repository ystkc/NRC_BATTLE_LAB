/** 只确认测试端口与已知测试进程，不终止任何其他进程。 */
const fs=require('node:fs'),path=require('node:path'),net=require('node:net');
const results={port:8774,checkedAt:new Date().toISOString(),serverProcesses:[],browserClose:'两个Chrome复现脚本均在finally await browser.close()后才写最终输出；无连接已有浏览器'};
for(const file of ['browser_output.json','browser_first_attempt.json']){
 const record=JSON.parse(fs.readFileSync(path.join(__dirname,file),'utf8'));
 if(record.serverPid){let alive=false;try{process.kill(record.serverPid,0);alive=true;}catch{}results.serverProcesses.push({source:file,pid:record.serverPid,alive});}
}
const probe=net.createServer();probe.once('error',error=>{results.portAvailable=false;results.error=error.message;fs.writeFileSync(path.join(__dirname,'cleanup.json'),JSON.stringify(results,null,2));process.exitCode=1;});
probe.listen(8774,'127.0.0.1',()=>probe.close(()=>{results.portAvailable=true;fs.writeFileSync(path.join(__dirname,'cleanup.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));}));
