<?php
class ExampleBridge extends BridgeAbstract {
    const NAME = 'Example Bridge';
    const URI = 'https://example.com';
    const DESCRIPTION = '最简单的 RSS-Bridge 自定义例子';
    const MAINTAINER = 'YourName';

    public function collectData(array $params) {
        $html = getSimpleHTMLDOM('https://example.com');
        foreach ($html->find('h1') as $element) {
            $item = new \Item();
            $item->title = $element->plaintext;
            $item->uri = 'https://example.com';
            $item->content = $element->plaintext;
            $this->items[] = $item;
        }
    }
}
