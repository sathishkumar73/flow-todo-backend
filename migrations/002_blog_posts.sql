-- Flow Todo — blog posts schema
CREATE TABLE IF NOT EXISTS blog_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(255) NOT NULL UNIQUE,
    title TEXT NOT NULL,
    excerpt TEXT,
    content TEXT NOT NULL,
    featured_image TEXT,
    thumbnail_url TEXT,
    category VARCHAR(100),
    tags TEXT[],
    seo_title TEXT,
    seo_description TEXT,
    published BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMPTZ,
    author_name VARCHAR(255) DEFAULT 'Flow Todo Team',
    author_avatar TEXT,
    read_time INT,
    view_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_blog_posts_slug        ON blog_posts(slug);
CREATE INDEX IF NOT EXISTS idx_blog_posts_published   ON blog_posts(published);
CREATE INDEX IF NOT EXISTS idx_blog_posts_published_at ON blog_posts(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_blog_posts_category    ON blog_posts(category);
