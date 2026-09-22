// 对已有服务做手工界面检查时显式提供测试账号，不再依赖内置管理员密码。
async function loginForTest(request, base) {
  const account = process.env.SHIYIN_TEST_ACCOUNT;
  const password = process.env.SHIYIN_TEST_PASSWORD;
  if (!account || !password) throw new Error('请设置 SHIYIN_TEST_ACCOUNT 和 SHIYIN_TEST_PASSWORD，使用已有测试账号。');
  const response = await request.post(`${base}/api/account/login`, { data: { account, password } });
  if (!response.ok()) throw new Error(`测试账号登录失败 (${response.status()})`);
  return response;
}
module.exports = { loginForTest };
