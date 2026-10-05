package main

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strconv"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Set TEST_DATABASE_URL to a dedicated disposable PostgreSQL database to run
// behavior-level API coverage. Each run owns a uniquely named schema and drops it.
func TestPostgresAPIAuthAndModeration(t *testing.T) {
	url := os.Getenv("TEST_DATABASE_URL")
	if url == "" {
		t.Skip("set TEST_DATABASE_URL to run PostgreSQL API integration coverage")
	}
	ctx := context.Background()
	base, err := pgxpool.New(ctx, url)
	if err != nil {
		t.Fatal(err)
	}
	defer base.Close()
	if err = base.Ping(ctx); err != nil {
		t.Fatal(err)
	}
	schema := "test_" + strings.ReplaceAll(uuid.NewString(), "-", "")
	if _, err = base.Exec(ctx, `CREATE SCHEMA "`+schema+`"`); err != nil {
		t.Fatal(err)
	}
	defer func() { _, _ = base.Exec(ctx, `DROP SCHEMA "`+schema+`" CASCADE`) }()
	config, err := pgxpool.ParseConfig(url)
	if err != nil {
		t.Fatal(err)
	}
	config.ConnConfig.RuntimeParams["search_path"] = schema
	db, err := pgxpool.NewWithConfig(ctx, config)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if err = migrate(ctx, db); err != nil {
		t.Fatal(err)
	}
	oldName, oldPassword := os.Getenv("ADMIN_USERNAME"), os.Getenv("ADMIN_PASSWORD")
	t.Setenv("ADMIN_USERNAME", "test-admin")
	t.Setenv("ADMIN_PASSWORD", "test-admin-password-123")
	defer func() { _ = os.Setenv("ADMIN_USERNAME", oldName); _ = os.Setenv("ADMIN_PASSWORD", oldPassword) }()
	s := &server{db: db, secret: []byte(strings.Repeat("integration-secret-", 3)), issuer: "integration", audience: "integration-web"}
	if err = s.bootstrapAdmin(ctx); err != nil {
		t.Fatal(err)
	}
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.Use(gin.Recovery())
	s.routes(router)
	request := func(method, path string, payload any, token string, cookie *http.Cookie) *httptest.ResponseRecorder {
		var body bytes.Buffer
		if payload != nil {
			if e := json.NewEncoder(&body).Encode(payload); e != nil {
				t.Fatal(e)
			}
		}
		req := httptest.NewRequest(method, path, &body)
		req.Header.Set("Content-Type", "application/json")
		if path == "/api/auth/refresh" {
			req.Header.Set("Origin", "http://127.0.0.1:5173")
		}
		if token != "" {
			req.Header.Set("Authorization", "Bearer "+token)
		}
		if cookie != nil {
			req.AddCookie(cookie)
		}
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		return w
	}
	register := request(http.MethodPost, "/api/auth/register", map[string]any{"username": "student1", "password": "long-test-password", "nickname": "测试同学", "student_number": "23010001"}, "", nil)
	if register.Code != http.StatusCreated {
		t.Fatalf("register status=%d body=%s", register.Code, register.Body.String())
	}
	var pair struct {
		Access string `json:"access_token"`
		User   user   `json:"user"`
	}
	if err = json.Unmarshal(register.Body.Bytes(), &pair); err != nil {
		t.Fatal(err)
	}
	if pair.Access == "" || pair.User.Student != "23010001" {
		t.Fatalf("unexpected registration response: %+v", pair)
	}
	refreshCookies := register.Result().Cookies()
	if len(refreshCookies) == 0 || !refreshCookies[0].HttpOnly || refreshCookies[0].SameSite != http.SameSiteStrictMode {
		t.Fatalf("refresh cookie missing required flags: %+v", refreshCookies)
	}
	oldRefresh := refreshCookies[0]
	rotated := request(http.MethodPost, "/api/auth/refresh", nil, "", oldRefresh)
	if rotated.Code != http.StatusOK {
		t.Fatalf("refresh status=%d body=%s", rotated.Code, rotated.Body.String())
	}
	newCookies := rotated.Result().Cookies()
	if len(newCookies) == 0 {
		t.Fatal("refresh did not rotate its cookie")
	}
	if replay := request(http.MethodPost, "/api/auth/refresh", nil, "", oldRefresh); replay.Code != http.StatusUnauthorized {
		t.Fatalf("replayed refresh token status=%d body=%s", replay.Code, replay.Body.String())
	}
	if revoked := request(http.MethodPost, "/api/auth/refresh", nil, "", newCookies[0]); revoked.Code != http.StatusUnauthorized {
		t.Fatalf("refresh family remained valid after replay status=%d", revoked.Code)
	}
	if got := request(http.MethodGet, "/api/auth/me", nil, pair.Access, nil); got.Code != http.StatusOK {
		t.Fatalf("me status=%d body=%s", got.Code, got.Body.String())
	}
	post := request(http.MethodPost, "/api/posts", map[string]any{"kind": "lost", "item_name": "遗失的钥匙", "description": "蓝色钥匙扣和两把钥匙"}, pair.Access, nil)
	if post.Code != http.StatusCreated {
		t.Fatalf("create post status=%d body=%s", post.Code, post.Body.String())
	}
	var created struct {
		ID int64 `json:"id"`
	}
	if err = json.Unmarshal(post.Body.Bytes(), &created); err != nil {
		t.Fatal(err)
	}
	login := request(http.MethodPost, "/api/auth/login", map[string]any{"username": "test-admin", "password": "test-admin-password-123"}, "", nil)
	if login.Code != http.StatusOK {
		t.Fatalf("admin login status=%d body=%s", login.Code, login.Body.String())
	}
	var adminPair struct {
		Access string `json:"access_token"`
	}
	if err = json.Unmarshal(login.Body.Bytes(), &adminPair); err != nil {
		t.Fatal(err)
	}
	if denied := request(http.MethodPost, "/api/admin/reviews/"+jsonNumber(created.ID)+"/approve", nil, pair.Access, nil); denied.Code != http.StatusForbidden {
		t.Fatalf("ordinary user review status=%d", denied.Code)
	}
	approved := request(http.MethodPost, "/api/admin/reviews/"+jsonNumber(created.ID)+"/approve", nil, adminPair.Access, nil)
	if approved.Code != http.StatusOK {
		t.Fatalf("approve status=%d body=%s", approved.Code, approved.Body.String())
	}
	public := request(http.MethodGet, "/api/posts/"+jsonNumber(created.ID), nil, "", nil)
	if public.Code != http.StatusOK || !strings.Contains(public.Body.String(), "遗失的钥匙") {
		t.Fatalf("public post status=%d body=%s", public.Code, public.Body.String())
	}
	if strings.Contains(public.Body.String(), "23010001") || strings.Contains(public.Body.String(), "student_number") {
		t.Fatalf("public response exposed the author's student number: %s", public.Body.String())
	}
	updated := request(http.MethodPut, "/api/posts/"+jsonNumber(created.ID), map[string]any{"kind": "lost", "item_name": "遗失的钥匙（已补充）", "description": "蓝色钥匙扣，两把钥匙，附有姓名牌。"}, pair.Access, nil)
	if updated.Code != http.StatusOK {
		t.Fatalf("submit revision status=%d body=%s", updated.Code, updated.Body.String())
	}
	stillOld := request(http.MethodGet, "/api/posts/"+jsonNumber(created.ID), nil, "", nil)
	if !strings.Contains(stillOld.Body.String(), "遗失的钥匙\"") || strings.Contains(stillOld.Body.String(), "遗失的钥匙（已补充）") {
		t.Fatalf("pending revision replaced approved content early: %s", stillOld.Body.String())
	}
	if approvedRevision := request(http.MethodPost, "/api/admin/reviews/"+jsonNumber(created.ID)+"/approve", nil, adminPair.Access, nil); approvedRevision.Code != http.StatusOK {
		t.Fatalf("approve revision status=%d body=%s", approvedRevision.Code, approvedRevision.Body.String())
	}
	updatedPublic := request(http.MethodGet, "/api/posts/"+jsonNumber(created.ID), nil, "", nil)
	if !strings.Contains(updatedPublic.Body.String(), "遗失的钥匙（已补充）") {
		t.Fatalf("approved revision was not made public: %s", updatedPublic.Body.String())
	}
	registerUser := func(username, student string) string {
		response := request(http.MethodPost, "/api/auth/register", map[string]any{"username": username, "password": "long-test-password", "nickname": username, "student_number": student}, "", nil)
		if response.Code != http.StatusCreated {
			t.Fatalf("register %s status=%d body=%s", username, response.Code, response.Body.String())
		}
		var result struct {
			Access string `json:"access_token"`
		}
		if e := json.Unmarshal(response.Body.Bytes(), &result); e != nil {
			t.Fatal(e)
		}
		return result.Access
	}
	logoutRegistration := request(http.MethodPost, "/api/auth/register", map[string]any{"username": "logout-user", "password": "long-test-password", "nickname": "logout-user", "student_number": "23010004"}, "", nil)
	logoutCookies := logoutRegistration.Result().Cookies()
	if logoutRegistration.Code != http.StatusCreated || len(logoutCookies) == 0 {
		t.Fatalf("prepare logout test failed: %d", logoutRegistration.Code)
	}
	if logout := request(http.MethodPost, "/api/auth/logout", nil, "", logoutCookies[0]); logout.Code != http.StatusOK {
		t.Fatalf("logout status=%d", logout.Code)
	}
	if afterLogout := request(http.MethodPost, "/api/auth/refresh", nil, "", logoutCookies[0]); afterLogout.Code != http.StatusUnauthorized {
		t.Fatalf("logout did not revoke refresh token family: %d", afterLogout.Code)
	}
	owner2 := registerUser("owner2", "23010002")
	stranger := registerUser("stranger", "23010003")
	outsider := registerUser("outsider", "23010005")
	found := request(http.MethodPost, "/api/posts", map[string]any{"kind": "found", "item_name": "拾获的水壶", "description": "绿色水壶，底部贴有姓名标签。"}, pair.Access, nil)
	if found.Code != http.StatusCreated {
		t.Fatalf("create found notice status=%d", found.Code)
	}
	var foundPost struct {
		ID int64 `json:"id"`
	}
	_ = json.Unmarshal(found.Body.Bytes(), &foundPost)
	if approvedFound := request(http.MethodPost, "/api/admin/reviews/"+jsonNumber(foundPost.ID)+"/approve", nil, adminPair.Access, nil); approvedFound.Code != http.StatusOK {
		t.Fatalf("approve found notice status=%d", approvedFound.Code)
	}
	claim1 := request(http.MethodPost, "/api/posts/"+jsonNumber(foundPost.ID)+"/requests", map[string]any{"explanation": "壶底有我的名字标签。", "contact_method": "email first@example.test"}, owner2, nil)
	claim2 := request(http.MethodPost, "/api/posts/"+jsonNumber(foundPost.ID)+"/requests", map[string]any{"explanation": "壶盖内侧有一道划痕。", "contact_method": "email second@example.test"}, stranger, nil)
	if claim1.Code != http.StatusCreated || claim2.Code != http.StatusCreated {
		t.Fatalf("create claims statuses=%d,%d", claim1.Code, claim2.Code)
	}
	var firstClaim, secondClaim struct {
		ID int64 `json:"id"`
	}
	_ = json.Unmarshal(claim1.Body.Bytes(), &firstClaim)
	_ = json.Unmarshal(claim2.Body.Bytes(), &secondClaim)
	if denied := request(http.MethodGet, "/api/requests/"+jsonNumber(firstClaim.ID), nil, outsider, nil); denied.Code != http.StatusForbidden {
		t.Fatalf("private request leaked to stranger, status=%d", denied.Code)
	}
	if unopened := request(http.MethodGet, "/api/admin/reports", nil, adminPair.Access, nil); strings.Contains(unopened.Body.String(), "first@example.test") {
		t.Fatalf("unreported request appeared to admin: %s", unopened.Body.String())
	}
	if authorView := request(http.MethodGet, "/api/posts/"+jsonNumber(foundPost.ID)+"/requests", nil, pair.Access, nil); authorView.Code != http.StatusOK || !strings.Contains(authorView.Body.String(), "first@example.test") {
		t.Fatalf("author could not view their requests: %d %s", authorView.Code, authorView.Body.String())
	}
	if reported := request(http.MethodPost, "/api/requests/"+jsonNumber(firstClaim.ID)+"/reports", map[string]any{"explanation": "请求内容需要管理员核查。"}, owner2, nil); reported.Code != http.StatusCreated {
		t.Fatalf("report private request status=%d", reported.Code)
	}
	adminQueue := request(http.MethodGet, "/api/admin/reports", nil, adminPair.Access, nil)
	if !strings.Contains(adminQueue.Body.String(), "first@example.test") {
		t.Fatalf("participant report did not reveal the target to admin: %s", adminQueue.Body.String())
	}
	accepted := request(http.MethodPost, "/api/requests/"+jsonNumber(firstClaim.ID)+"/accept", nil, pair.Access, nil)
	if accepted.Code != http.StatusOK {
		t.Fatalf("accept claim status=%d body=%s", accepted.Code, accepted.Body.String())
	}
	secondState := request(http.MethodGet, "/api/requests/"+jsonNumber(secondClaim.ID), nil, stranger, nil)
	if secondState.Code != http.StatusOK || !strings.Contains(secondState.Body.String(), "已拒绝") {
		t.Fatalf("other claim was not closed: %d %s", secondState.Code, secondState.Body.String())
	}
	closed := request(http.MethodPost, "/api/posts/"+jsonNumber(foundPost.ID)+"/status", map[string]any{"status": "待认领"}, pair.Access, nil)
	if closed.Code != http.StatusConflict {
		t.Fatalf("resolved post was reopened, status=%d", closed.Code)
	}
	withdrawn := request(http.MethodDelete, "/api/posts/"+jsonNumber(foundPost.ID), nil, pair.Access, nil)
	if withdrawn.Code != http.StatusOK || !strings.Contains(withdrawn.Body.String(), `"withdrawn":true`) {
		t.Fatalf("post history was not retained: %d %s", withdrawn.Code, withdrawn.Body.String())
	}
	if hidden := request(http.MethodGet, "/api/posts/"+jsonNumber(foundPost.ID), nil, "", nil); hidden.Code != http.StatusNotFound {
		t.Fatalf("withdrawn post remained public, status=%d", hidden.Code)
	}
}

func jsonNumber(n int64) string { return strconv.FormatInt(n, 10) }
