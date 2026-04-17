# EXAMPLE.md

This file shows the `koinonia` social media app as the main worked example for
`erza`.

It is not a toy counter or a tiny feed stub. It is the actual shape of the
social app this repo has been evolving, rewritten here as an annotated `.erza`
source walkthrough.

## Comment Syntax

`erza` source comments use standard HTML comment syntax.

They are ignored by the compiler and runtime, so developers can leave notes in a
real `index.erza` file without affecting the rendered app.

```erza
<!-- This is an erza source comment. -->
```

## Annotated Koinonia index.erza

This is a commented version of the `koinonia/index.erza` structure.

It keeps the actual Koinonia product shape:

- one `index.erza`
- login-gated tabs
- modal-only forms
- a feed and profile view
- thread viewing and replying
- profile editing
- a splash animation

The repetitive mirrored modal families are shortened in a few places to keep the
example readable, but the syntax and app structure are the real Koinonia model.

```erza
<Screen title="Koinonia">
  <!-- Splash runs before the main app shell appears. -->
  <Splash duration-ms="1400">
    <!-- SplashAnimation is raw ASCII frame animation. -->
    <SplashAnimation fps="7">
      <Frame>
 _  __      _                       _
| |/ /___  (_)___  ____  ____  ____(_)_ _
|   / __ \/ / __ \/ __ \/ __ \/ __/ /  ' \\
|   / /_/ / / / / / /_/ / / / / /_/ / /| |
|_|\\_\\____/_/_/ /_/\____/_/ /_/\__/_/_/ |_|

terminal social commons .
      </Frame>
      <Frame>
 _  __      _                       _
| |/ /___  (_)___  ____  ____  ____(_)_ _
|   / __ \/ / __ \/ __ \/ __ \/ __/ /  ' \\
|   / /_/ / / / / / /_/ / / / / /_/ / /| |
|_|\\_\\____/_/_/ /_/\____/_/ /_/\__/_/_/ |_|

terminal social commons ..
      </Frame>
      <Frame>
 _  __      _                       _
| |/ /___  (_)___  ____  ____  ____(_)_ _
|   / __ \/ / __ \/ __ \/ __ \/ __/ /  ' \\
|   / /_/ / / / / / /_/ / / / / /_/ / /| |
|_|\\_\\____/_/_/ /_/\____/_/ /_/\__/_/_/ |_|

terminal social commons ...
      </Frame>
    </SplashAnimation>
  </Splash>

  <!-- backend(...) reads data from the app backend into the template scope. -->
  <? auth = backend("auth.viewer") ?>
  <? status = backend("ui.status") ?>
  <? overview = backend("network.overview") ?>
  <? highlights = backend("mission.highlights") ?>

  <!-- Template control flow uses PHP-style delimiters. -->
  <? if auth.logged_in ?>
    <? profile = backend("profiles.current") ?>
    <? timeline = backend("feed.timeline") ?>

    <!-- Top-level Section blocks are the app tabs. -->
    <Section title="Feed" tab-order="1" default-tab="true">
      <Header>Town Square</Header>
      <Text><?= status ?></Text>

      <!-- ButtonRow is the canonical horizontal action strip. -->
      <ButtonRow>
        <!-- ui.open_modal is a runtime-local action, not a backend call. -->
        <Action on:press="ui.open_modal" modal:id="create-post">New post</Action>
      </ButtonRow>

      <Text><?= overview.posts ?> posts, <?= overview.replies ?> replies, and <?= overview.people ?> residents are live in the square.</Text>

      <? if timeline ?>
        <? for post in timeline ?>
          <!-- Nested Section blocks act like boxed content panels, not tabs. -->
          <Section title="@<?= post.handle ?>">
            <Text><?= post.body ?></Text>
            <Text><?= post.likes ?> likes | <?= post.reply_count ?> replies</Text>

            <ButtonRow align="right">
              <!-- Non-ui actions are backend action names. -->
              <Action on:press="feed.like" post:id="<?= post.id ?>">Like</Action>
              <Action on:press="ui.open_modal" modal:id="feed-thread-<?= post.id ?>">View Replies</Action>
              <Action on:press="ui.open_modal" modal:id="feed-compose-post-<?= post.id ?>">Reply</Action>
            </ButtonRow>
          </Section>
        <? endfor ?>
      <? else ?>
        <Text>No posts yet. Open the modal above and start the square.</Text>
      <? endif ?>
    </Section>

    <Section title="Profile" tab-order="0">
      <!-- AsciiArt preserves whitespace and is ideal for profile pictures. -->
      <AsciiArt><?= profile.picture ?></AsciiArt>
      <Header>@<?= profile.handle ?></Header>
      <Text><?= profile.description or "No description set yet." ?></Text>

      <ButtonRow>
        <Action on:press="ui.open_modal" modal:id="create-post">New post</Action>
        <Action on:press="ui.open_modal" modal:id="profile-edit">Edit profile</Action>
      </ButtonRow>

      <Text><?= status ?></Text>

      <? if profile.posts ?>
        <? for post in profile.posts ?>
          <Section title="@<?= post.handle ?>">
            <Text><?= post.body ?></Text>
            <Text><?= post.likes ?> likes | <?= post.reply_count ?> replies</Text>
            <ButtonRow align="right">
              <Action on:press="feed.like" post:id="<?= post.id ?>">Like</Action>
              <Action on:press="ui.open_modal" modal:id="profile-thread-<?= post.id ?>">View Replies</Action>
              <Action on:press="ui.open_modal" modal:id="profile-compose-post-<?= post.id ?>">Reply</Action>
            </ButtonRow>
          </Section>
        <? endfor ?>
      <? else ?>
        <Text>No posts yet. Open the modal above and start your thread history.</Text>
      <? endif ?>
    </Section>

    <!-- A Section can also be a direct-action tab with no real page body. -->
    <Section title="Logout" tab-order="2">
      <Action on:press="auth.logout">Log out</Action>
    </Section>

    <? for post in timeline ?>
      <!-- View modals are read-only or may only open form-only modals. -->
      <Modal id="feed-thread-<?= post.id ?>" title="Replies for @<?= post.handle ?>">
        <Header>@<?= post.handle ?></Header>
        <Text><?= post.body ?></Text>
        <Text><?= post.likes ?> likes | <?= post.reply_count ?> replies</Text>

        <? if post.replies ?>
          <? for reply in post.replies ?>
            <Section title="@<?= reply.handle ?>">
              <Text><?= reply.body ?></Text>
              <Text><?= reply.likes ?> likes | <?= reply.reply_count ?> replies</Text>

              <? for nested in reply.replies ?>
                <Section title="@<?= nested.handle ?>">
                  <Text><?= nested.body ?></Text>
                  <Text><?= nested.likes ?> likes</Text>
                </Section>
              <? endfor ?>

              <ButtonRow align="right">
                <Action on:press="ui.open_modal" modal:id="feed-compose-reply-<?= reply.id ?>">Reply on Thread</Action>
              </ButtonRow>
            </Section>
          <? endfor ?>
        <? else ?>
          <Text>No replies yet.</Text>
        <? endif ?>
      </Modal>

      <!-- Form modals may contain exactly one Form. -->
      <Modal id="feed-compose-post-<?= post.id ?>" title="Reply">
        <Form action="/threads/reply">
          <!-- Hidden inputs pass backend state without showing UI controls. -->
          <Input name="thread_slug" type="hidden" value="<?= post.slug ?>" />

          <!-- Normal inputs render as editable fields in the modal. -->
          <Input name="body" type="text" label="Reply" required="mandatory" />

          <!-- In forms, ButtonRow contains Submit buttons, not Action buttons. -->
          <ButtonRow align="right">
            <Submit>Post reply</Submit>
          </ButtonRow>
        </Form>
      </Modal>

      <!-- Reply-on-reply shows boxed context first, then a form. -->
      <? for reply in post.replies ?>
        <Modal id="feed-compose-reply-<?= reply.id ?>" title="Reply on Thread">
          <Form action="/threads/reply">
            <Section title="@<?= post.handle ?>">
              <Text><?= post.body ?></Text>
              <Text><?= post.likes ?> likes | <?= post.reply_count ?> replies</Text>

              <Section title="@<?= reply.handle ?>">
                <Text><?= reply.body ?></Text>
                <Text><?= reply.likes ?> likes | <?= reply.reply_count ?> replies</Text>
              </Section>
            </Section>

            <Input name="thread_slug" type="hidden" value="<?= post.slug ?>" />
            <Input name="parent_reply_id" type="hidden" value="<?= reply.id ?>" />
            <Input name="body" type="text" label="Reply" required="mandatory" />

            <ButtonRow align="right">
              <Submit>Post reply</Submit>
            </ButtonRow>
          </Form>
        </Modal>
      <? endfor ?>
    <? endfor ?>

    <!-- Profile editing is also a form-only modal. -->
    <Modal id="profile-edit" title="Edit Profile">
      <Form action="/profile/edit">
        <Input name="description" type="text" label="Description" value="<?= profile.description ?>" />
        <Input name="profile_picture" type="ascii-art" label="Profile Picture" value="<?= profile.picture ?>" />
        <ButtonRow align="right">
          <Submit>Save profile</Submit>
        </ButtonRow>
      </Form>
    </Modal>

    <Modal id="create-post" title="New Post">
      <Form action="/posts">
        <Input name="body" type="text" label="Post" required="mandatory" />
        <ButtonRow align="right">
          <Submit>Post to Koinonia</Submit>
        </ButtonRow>
      </Form>
    </Modal>

  <? else ?>
    <!-- Logged-out tabs are just a different top-level section set. -->
    <Section title="Why Koinonia">
      <Header>One terminal-native town square.</Header>
      <Text><?= overview.posts ?> posts, <?= overview.replies ?> replies, and <?= overview.people ?> residents are already live.</Text>

      <? for highlight in highlights ?>
        <Text><?= highlight.title ?></Text>
        <Text><?= highlight.body ?></Text>
      <? endfor ?>
    </Section>

    <Section title="Login / Sign Up">
      <Action on:press="ui.open_modal" modal:id="auth-access">Open account access</Action>
    </Section>

    <Modal id="auth-access" title="Login / Sign Up">
      <Form action="/auth/access">
        <Input name="username" type="text" label="Username" required="mandatory" />
        <Input name="password" type="password" label="Password" required="mandatory" />
        <ButtonRow align="right">
          <Submit>Enter Koinonia</Submit>
        </ButtonRow>
      </Form>
    </Modal>
  <? endif ?>
</Screen>
```

## Syntax patterns to notice

- `<? ... ?>` assigns variables or controls flow at template-render time.
- `<?= ... ?>` outputs a value directly into the markup.
- `<Section>` means tabs at the top level and boxed panels when nested.
- `<Modal>` lives only at the screen root.
- `<Form>` lives only inside a modal.
- `<Input type="ascii-art">` is still an input field, just with multi-line ASCII editing semantics.
- `<Action on:press="ui.open_modal">` is intercepted by the runtime.
- `<Action on:press="feed.like">` is a backend action command.
- `<ButtonRow>` is the standard place for actions and submits.
- `tab-order` controls tab ordering and `default-tab="true"` chooses the landing tab.

## What the backend needs to provide

This `.erza` file assumes a backend that can answer these reads and writes:

Read handlers:

- `auth.viewer`
- `ui.status`
- `network.overview`
- `mission.highlights`
- `profiles.current`
- `feed.timeline`

Write endpoints and actions:

- `auth.logout`
- `/auth/access`
- `/posts`
- `/profile/edit`
- `/threads/reply`
- `feed.like`

That split is the important design line in `erza`:

- the `.erza` file defines the UI structure
- the backend provides state and side effects
- the runtime owns navigation, focus, modal behavior, and form handling
