# BOSS 直聘浏览器控制台导出脚本

一行命令粘贴到浏览器控制台，自动导出当前页的岗位数据。

## 使用方法

1. 打开 https://www.zhipin.com/hangzhou/ （或其他城市站）
2. 搜索关键词（如"外贸业务员"）
3. 按 **F12** 打开开发者工具
4. 点 **Console（控制台）** 标签
5. 粘贴下面这段代码，按 **回车**
6. 自动下载 JSON 文件

## 代码

```javascript
var cards=document.querySelectorAll('.job-card-wrapper'),jobs=[];cards.forEach(function(c){var j={};['.job-name','.company-name','.salary','.job-area'].forEach(function(s){var e=c.querySelector(s);if(e)j[s.replace('.','')]=e.innerText.trim()});var t=[];c.querySelectorAll('.job-limit .tag-item').forEach(function(e){t.push(e.innerText.trim())});if(t.length)j.tags=t;var a=c.querySelector('a.job-card-left');if(a){var h=a.getAttribute('href');if(h)j.url='https://www.zhipin.com'+(h.startsWith('/')?h:'/'+h)}if(j['job-name'])jobs.push(j)});if(jobs.length){var b=new Blob([JSON.stringify(jobs,null,2)],{type:'application/json'}),u=URL.createObjectURL(b),x=document.createElement('a');x.href=u;x.download='bosszp_'+(new Date().toISOString().slice(0,10))+'.json';document.body.appendChild(x);x.click();document.body.removeChild(x);URL.revokeObjectURL(u);console.log('✅ 已导出 '+jobs.length+' 条岗位数据')}else{console.log('❌ 当前页面没有找到岗位卡片')}
```

导出的 JSON 可以用 `python analyze.py data/xxx.json` 分析。

## 分步版（可读性更好，但要多粘贴几次）

如果一行太长不方便，也可以分步粘贴：

```javascript
// 第 1 步：找岗位卡片
var cards = document.querySelectorAll('.job-card-wrapper');
console.log('找到 ' + cards.length + ' 张岗位卡片');
```

```javascript
// 第 2 步：提取数据
var jobs = [];
cards.forEach(function(card) {
  var job = {};
  job.title = card.querySelector('.job-name')?.innerText?.trim() || '';
  job.company = card.querySelector('.company-name')?.innerText?.trim() || '';
  job.salary = card.querySelector('.salary')?.innerText?.trim() || '';
  job.location = card.querySelector('.job-area')?.innerText?.trim() || '';
  var tags = [];
  card.querySelectorAll('.job-limit .tag-item').forEach(function(t) {
    tags.push(t.innerText.trim());
  });
  if (tags.length) job.tags = tags;
  var a = card.querySelector('a.job-card-left');
  if (a) {
    var h = a.getAttribute('href');
    if (h) job.url = 'https://www.zhipin.com' + (h.startsWith('/') ? h : '/' + h);
  }
  if (job.title) jobs.push(job);
});
console.log('提取了 ' + jobs.length + ' 条');
```

```javascript
// 第 3 步：下载
var blob = new Blob([JSON.stringify(jobs, null, 2)], {type: 'application/json'});
var url = URL.createObjectURL(blob);
var a = document.createElement('a');
a.href = url;
a.download = 'bosszp_' + new Date().toISOString().slice(0,10) + '.json';
document.body.appendChild(a);
a.click();
document.body.removeChild(a);
URL.revokeObjectURL(url);
console.log('✅ 已导出 ' + jobs.length + ' 条岗位数据');
```
