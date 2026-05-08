# BOSS 直聘书签脚本（Bookmarklet）

比 Python 爬虫更简单的方式：拖一个书签到浏览器书签栏，在 BOSS 直聘页面点一下就导出数据。

## 安装方法

1. 复制下面这段代码
2. 在浏览器书签栏右键 → **添加页面**（或 **新建书签**）
3. **名称**填：`BOSS导出`
4. **网址/URL**填：粘贴下面整段代码
5. 保存

## Bookmarklet 代码

```javascript
javascript:(function(){
  let jobs=[];
  let cards=document.querySelectorAll('.job-card-wrapper');
  if(!cards.length)cards=document.querySelectorAll('[class*="job-card"]');
  cards.forEach(c=>{
    let j={};
    let getName=(sel)=>c.querySelector(sel)?.innerText?.trim()||'';
    j.title=getName('.job-name')||getName('[class*="job-name"]');
    j.company=getName('.company-name')||getName('[class*="company-name"]');
    j.salary=getName('.salary')||getName('[class*="salary"]');
    j.location=getName('.job-area')||getName('[class*="job-area"]');
    let tags=[];c.querySelectorAll('.job-limit .tag-item,[class*="tag-item"]').forEach(t=>tags.push(t.innerText.trim()));if(tags.length)j.tags=tags;
    let a=c.querySelector('a.job-card-left');if(a){let h=a.getAttribute('href');if(h)j.url=h.startsWith('/')?'https://www.zhipin.com'+h:h;}
    if(j.title)jobs.push(j);
  });
  if(!jobs.length){alert('没有找到岗位数据。请确认你在 BOSS 直聘的搜索结果页面上。');return;}
  let blob=new Blob([JSON.stringify(jobs,null,2)],{type:'application/json'});
  let url=URL.createObjectURL(blob);
  let a=document.createElement('a');a.href=url;a.download='bosszp_jobs_'+new Date().toISOString().slice(0,19).replace(/[:-]/g,'')+'.json';
  document.body.appendChild(a);a.click();document.body.removeChild(a);URL.revokeObjectURL(url);
  alert('已导出 '+jobs.length+' 条岗位数据！');
})();
```

## 使用流程

```
1. 在浏览器中打开 https://www.zhipin.com 并登录
2. 搜索关键词（如"技术文档工程师"）
3. 点击书签栏的 "BOSS导出"
4. 自动下载 JSON 文件
5. 把 JSON 放到 data/ 目录
6. 运行分析：python analyze.py data/xxx.json
```

## 注意

- 只会导出**当前页面**上显示的岗位（约 30 条）
- 需要翻页的话，翻到下一页再点一次书签
- 多次导出的 JSON 可以自行合并
