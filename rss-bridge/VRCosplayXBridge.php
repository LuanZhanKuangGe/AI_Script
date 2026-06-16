<?php
class VRCosplayXBridge extends BridgeAbstract {
    const NAME = 'VRCosplayX';
    const URI = 'https://vrcosplayx.com';
    const DESCRIPTION = 'VRCosplayX 最新 Cosplay 视频';
    const MAINTAINER = 'YourName';
    const CACHE_TIMEOUT = 3600;

    const PARAMETERS = [[
        'page' => [
            'name' => '页码（从 1 开始）',
            'type' => 'number',
            'defaultValue' => 1,
        ],
    ]];

    public function collectData() {
        $page = $this->getInput('page') ?: 1;
        $url = self::URI . '/cosplaypornvideos?order=newest';
        if ($page > 1) {
            $url = self::URI . '/cosplaypornvideos/' . $page . '?order=newest';
        }

        $html = getSimpleHTMLDOM($url);
        if (!$html) {
            return;
        }

        foreach ($html->find('div.video-card') as $card) {
            $a = $card->find('a.video-card-title', 0);
            if (!$a) {
                continue;
            }

            $item = [];
            $item['uri'] = self::URI . $a->href;

            $title = trim($a->title ?? $a->plaintext);
            $item['title'] = $title ?: 'VRCosplayX Video';

            $img = $card->find('img.video-card-image', 0);
            $imgUrl = '';
            if ($img) {
                $imgUrl = $img->getAttribute('data-src') ?: $img->src;
                $item['enclosures'] = [$imgUrl];
            }

            $desc = $card->find('p.video-card-description', 0);
            $description = $desc ? trim($desc->plaintext) : '';

            $castLinks = [];
            foreach ($card->find('div.video-card-details--cast-list a.video-card-link') as $castA) {
                $castLinks[] = trim($castA->plaintext);
            }

            $tags = [];
            foreach ($card->find('p.video-card-tags a') as $tagA) {
                $tags[] = trim($tagA->plaintext);
            }

            $dateSpan = $card->find('span.video-card-upload-date', 0);
            if ($dateSpan) {
                $dateContent = $dateSpan->getAttribute('content');
                if ($dateContent) {
                    $item['timestamp'] = strtotime($dateContent);
                }
            }

            $content = '';
            if ($imgUrl) {
                $content .= '<p><img src="' . htmlspecialchars($imgUrl) . '"></p>';
            }
            if ($castLinks) {
                $content .= '<p><strong>Cast:</strong> ' . implode(', ', $castLinks) . '</p>';
            }
            if ($description) {
                $content .= '<p>' . htmlspecialchars($description) . '</p>';
            }
            if ($tags) {
                $content .= '<p><strong>Tags:</strong> ' . implode(', ', array_map('htmlspecialchars', $tags)) . '</p>';
            }
            $item['content'] = $content;

            $this->items[] = $item;
        }
    }
}