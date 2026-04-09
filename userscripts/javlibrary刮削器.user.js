// ==UserScript==
// @name         JAVLibrary 图片下载
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  下载封面图片和nfo文件
// @match        https://www.javlibrary.com/cn/*
// @grant        GM_download
// @require      https://cdn.bootcdn.net/ajax/libs/jquery/3.6.0/jquery.min.js
// ==/UserScript==

(function() {
    'use strict';

    const selector = 'li a[href="publicgroups.php"]';
    const $li = $(selector).parent();

    if ($li.length) {
        const $newLi = $('<li></li>');
        const $link = $('<a href="javascript:void(0);">下载封面</a>');
        
        $link.on('click', function() {
            const $img = $('#video_jacket_img')[0];
            const imgUrl = $img.src;
            
            if (!imgUrl) {
                alert('未找到图片');
                return;
            }
            
            const title = $('#video_title h3.post-title a').text();
            const ext = imgUrl.split('.').pop();
            const filename = `${title}-fanart.${ext}`;
            
            const videoId = $('#video_id .text').text().trim();
            const date = $('#video_date .text').text().trim();
            const length = $('#video_length .text').text().trim();
            const director = $('#video_director .text').text().trim();
            const maker = $('#video_maker .text').text().trim();
            const label = $('#video_label .text').text().trim();
            const genres = [];
            $('#video_genres .genre a').each(function() {
                genres.push($(this).text().trim());
            });
            const cast = [];
            $('#video_cast .star a').each(function() {
                cast.push($(this).text().trim());
            });
            
            const nfoContent = `<?xml version="1.0" encoding="UTF-8"?>
<movie>
  <title>${escapeXml(title)}</title>
  <originaltitle>${escapeXml(title)}</originaltitle>
  <id>${escapeXml(videoId)}</id>
  <year>${date ? escapeXml(date.split('-')[0]) : ''}</year>
  <premiered>${escapeXml(date)}</premiered>
  <runtime>${escapeXml(length.replace(/[^0-9]/g, ''))}</runtime>
  <studio>${escapeXml(maker)}</studio>
  <publisher>${escapeXml(label)}</publisher>
  <director>${escapeXml(director)}</director>
  <genre>
    ${genres.map(g => escapeXml(g)).join('\n    ')}</genre>
  <actor>${cast.map(c => '\n    <name>' + escapeXml(c) + '</name>').join('')}</actor>
  <set></set>
  <plot></plot>
  <outline></outline>
  <thumb aspect="fanart">${escapeXml(imgUrl)}</thumb>
</movie>`;
            
            console.log('[DEBUG] nfo内容:', nfoContent);
            
            const nfoFilename = `${title}.nfo`;
            const nfoBlob = new Blob([nfoContent], { type: 'text/xml' });
            console.log('[DEBUG] nfo blob大小:', nfoBlob.size);
            
            const nfoUrl = URL.createObjectURL(nfoBlob);
            const nfoLink = document.createElement('a');
            nfoLink.href = nfoUrl;
            nfoLink.download = nfoFilename;
            console.log('[DEBUG] 准备下载nfo:', nfoFilename);
            nfoLink.click();
            URL.revokeObjectURL(nfoUrl);
            console.log('[DEBUG] nfo下载完成');
            
            GM_download({ url: imgUrl, name: filename, saveAs: true });
        });
        
        $newLi.append($link);
        $li.after($newLi);
    }
    
    function escapeXml(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;')
                  .replace(/</g, '&lt;')
                  .replace(/>/g, '&gt;')
                  .replace(/"/g, '&quot;')
                  .replace(/'/g, '&apos;');
    }
})();
