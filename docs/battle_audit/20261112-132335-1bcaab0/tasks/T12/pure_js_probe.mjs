/** 对真实浏览器提取的候选值调用同一纯筛选函数。 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const {createRosterEditor}=await import(pathToFileURL(path.resolve(here,'../../../../../nrc_server/static/roster.js')));
const fixture=JSON.parse(fs.readFileSync(path.join(here,'supplement_output.json'),'utf8'));
const editor=createRosterEditor({});
const choices=fixture.editor.nature,query=choices[0].pinyin;
const actual=editor.choiceMatches(choices,query).map(x=>x.name);
fs.writeFileSync(path.join(here,'pure_js_output.json'),JSON.stringify({query,choices,actual,expected:[choices[0].name],unique:new Set(actual).size===actual.length},null,2));
console.log(JSON.stringify({query,actual}));
