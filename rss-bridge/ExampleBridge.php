<?php
class ExampleBridge extends BridgeAbstract {
    const NAME = 'Example Bridge';
    const URI = 'https://example.com';
    const DESCRIPTION = '最简单的 RSS-Bridge 自定义例子';
    const MAINTAINER = 'YourName';

    public function collectData() {
        $html = getSimpleHTMLDOM(self::URI);
        if (!$html) {
            return;
        }
        foreach ($html->find('h1') as $element) {
            $this->items[] = [
                'uri' => self::URI,
                'title' => $element->plaintext,
                'content' => $element->plaintext,
            ];
        }
    }
}