# sitemap_generator.py - Dynamic sitemap generation

from datetime import datetime
from typing import List, Dict
import httpx

async def generate_dynamic_sitemap(posts_api_url: str) -> str:
    """
    Генерирует динамический sitemap.xml с актуальными товарами.
    
    Args:
        posts_api_url: URL posts-service API
        
    Returns:
        XML string с sitemap
    """
    
    # Статические страницы
    static_urls = [
        {
            "loc": "https://test.yuniversia.eu/",
            "lastmod": datetime.now().strftime("%Y-%m-%d"),
            "changefreq": "daily",
            "priority": "1.0"
        },
        {
            "loc": "https://test.yuniversia.eu/terms",
            "lastmod": "2025-12-04",
            "changefreq": "monthly",
            "priority": "0.5"
        },
        {
            "loc": "https://test.yuniversia.eu/imei-check",
            "lastmod": "2025-12-04",
            "changefreq": "weekly",
            "priority": "0.8"
        }
    ]
    
    # Получаем список товаров из posts-service
    dynamic_urls = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{posts_api_url}/api/v1/iphone/list")
            if response.status_code == 200:
                posts = response.json()
                for post in posts:
                    # Добавляем страницу товара
                    dynamic_urls.append({
                        "loc": f"https://test.yuniversia.eu/product?id={post['id']}",
                        "lastmod": post.get('updated_at', post.get('created_at', datetime.now().strftime("%Y-%m-%d"))),
                        "changefreq": "weekly",
                        "priority": "0.9",
                        "image": post.get('photos', [None])[0] if post.get('photos') else None,
                        "image_title": f"{post.get('model', 'iPhone')} {post.get('memory', '')}GB"
                    })
    except Exception as e:
        print(f"Error fetching posts for sitemap: {e}")
    
    # Генерируем XML
    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
    ]
    
    # Добавляем статические страницы
    for url in static_urls:
        xml_parts.append('    <url>')
        xml_parts.append(f'        <loc>{url["loc"]}</loc>')
        xml_parts.append(f'        <lastmod>{url["lastmod"]}</lastmod>')
        xml_parts.append(f'        <changefreq>{url["changefreq"]}</changefreq>')
        xml_parts.append(f'        <priority>{url["priority"]}</priority>')
        xml_parts.append('    </url>')
    
    # Добавляем динамические страницы товаров
    for url in dynamic_urls:
        xml_parts.append('    <url>')
        xml_parts.append(f'        <loc>{url["loc"]}</loc>')
        xml_parts.append(f'        <lastmod>{url["lastmod"][:10]}</lastmod>')
        xml_parts.append(f'        <changefreq>{url["changefreq"]}</changefreq>')
        xml_parts.append(f'        <priority>{url["priority"]}</priority>')
        
        # Добавляем изображение если есть
        if url.get("image"):
            xml_parts.append('        <image:image>')
            xml_parts.append(f'            <image:loc>{url["image"]}</image:loc>')
            xml_parts.append(f'            <image:title>{url["image_title"]}</image:title>')
            xml_parts.append('        </image:image>')
        
        xml_parts.append('    </url>')
    
    xml_parts.append('</urlset>')
    
    return '\n'.join(xml_parts)
