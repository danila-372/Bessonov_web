def patch_posts(mocker, posts_list):
    return mocker.patch("app.posts_list", return_value=posts_list, autospec=True)


def test_posts_index_status_code(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    response = client.get("/posts")

    assert response.status_code == 200


def test_posts_index_heading(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    response = client.get("/posts")

    assert "Последние посты" in response.text


def test_posts_index_template(client, captured_templates, mocker, posts_list):
    with captured_templates as templates:
        patch_posts(mocker, posts_list)
        
        client.get('/posts')

        assert len(templates) == 1
        template, context = templates[0]
        assert template.name == 'posts.html'


def test_posts_index_context_title(client, captured_templates, mocker, posts_list):
    with captured_templates as templates:
        patch_posts(mocker, posts_list)

        client.get('/posts')

        _, context = templates[0]
        assert context['title'] == 'Посты'


def test_posts_index_context_posts(client, captured_templates, mocker, posts_list):
    with captured_templates as templates:
        patch_posts(mocker, posts_list)

        client.get('/posts')

        _, context = templates[0]
        assert context['posts'] == posts_list


def test_posts_index_renders_post_titles(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    response = client.get('/posts')

    assert posts_list[0]['title'] in response.text
    assert posts_list[1]['title'] in response.text


def test_posts_index_renders_post_authors(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    response = client.get('/posts')

    assert posts_list[0]['author'] in response.text
    assert posts_list[1]['author'] in response.text


def test_posts_index_renders_formatted_dates(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    response = client.get('/posts')

    assert '10.03.2025' in response.text
    assert '05.12.2024' in response.text


def test_posts_index_links_to_post_pages(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    response = client.get('/posts')

    assert '/posts/0' in response.text
    assert '/posts/1' in response.text


def test_post_detail_status_code(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    response = client.get('/posts/0')

    assert response.status_code == 200


def test_post_detail_template(client, captured_templates, mocker, posts_list):
    with captured_templates as templates:
        patch_posts(mocker, posts_list)

        client.get('/posts/0')

        assert len(templates) == 1
        template, _ = templates[0]
        assert template.name == 'post.html'


def test_post_detail_context(client, captured_templates, mocker, posts_list):
    with captured_templates as templates:
        patch_posts(mocker, posts_list)

        client.get('/posts/0')

        _, context = templates[0]
        assert context['title'] == posts_list[0]['title']
        assert context['post'] == posts_list[0]


def test_post_detail_renders_post_data(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    post = posts_list[0]
    response = client.get('/posts/0')

    assert post['title'] in response.text
    assert post['text'] in response.text
    assert post['author'] in response.text


def test_post_detail_renders_formatted_publication_date(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    response = client.get('/posts/0')

    assert '10.03.2025' in response.text
    assert '2025-03-10' not in response.text


def test_post_detail_renders_image(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    response = client.get('/posts/0')

    assert 'images/first.jpg' in response.text
    assert f'alt="{posts_list[0]["title"]}"' in response.text


def test_post_detail_renders_comment_form(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    response = client.get('/posts/0')

    assert 'Оставьте комментарий' in response.text
    assert 'name="comment"' in response.text
    assert 'Отправить' in response.text


def test_post_detail_renders_comments(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    comment = posts_list[0]['comments'][0]
    response = client.get('/posts/0')

    assert comment['author'] in response.text
    assert comment['text'] in response.text


def test_post_detail_renders_replies(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    reply = posts_list[0]['comments'][0]['replies'][0]
    response = client.get('/posts/0')

    assert reply['author'] in response.text
    assert reply['text'] in response.text


def test_post_detail_without_comments_shows_placeholder(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    response = client.get('/posts/1')

    assert 'Комментариев пока нет.' in response.text


def test_footer_renders_author_and_group(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    response = client.get('/posts/0')

    assert 'Бессонов Данила Алексеевич, группа 241-372' in response.text


def test_unknown_post_returns_404(client, mocker, posts_list):
    patch_posts(mocker, posts_list)
    response = client.get('/posts/99')

    assert response.status_code == 404
